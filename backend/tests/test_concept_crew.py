"""Tests for concept crew and deck worker. Mocks LLM so no API key required."""

import json
from unittest.mock import patch

from crewai import Process

from app.crews.concept_crew import build_concept_crew, run_concept_crew
from app.crews.outputs import ApproveReject, CardConcept, RefinedPrompt
from app.workers.deck_worker import get_next_deck_job, process_deck_job


def test_build_concept_crew_has_two_agents_and_two_tasks():
    crew = build_concept_crew()
    assert len(crew.agents) == 2
    assert len(crew.tasks) == 2
    assert crew.process == Process.sequential


def test_run_concept_crew_returns_card_concept_with_all_fields():
    from app.crews.outputs import ImagePromptOutput, MeaningDescription

    style_bible_snippet = "# Style Bible\n\n## Palette\nDark greens."
    fake_meaning = MeaningDescription(meaning="New beginnings, spontaneity.", description="A traveler at a cliff edge.")
    fake_image = ImagePromptOutput(image_prompt="A lone figure at a cliff, dark green palette.")
    fake_result = type("CrewOutput", (), {
        "tasks_output": [
            type("T", (), {"pydantic": fake_meaning})(),
            type("T", (), {"pydantic": fake_image})(),
        ]
    })()
    mock_crew = type("MockCrew", (), {"kickoff": lambda self, **kw: fake_result})()
    with patch("app.crews.concept_crew.build_concept_crew", return_value=mock_crew):
        result = run_concept_crew(
            style_bible=style_bible_snippet,
            card_name="The Fool",
            card_index=0,
        )
    assert result.name == "The Fool"
    assert result.meaning == "New beginnings, spontaneity."
    assert result.description == "A traveler at a cliff edge."
    assert result.image_prompt == "A lone figure at a cliff, dark green palette."


def test_process_deck_job_updates_cards_with_concept():
    from fastapi.testclient import TestClient

    from app import models
    from app.main import app
    from tests.shared_db import SessionLocal
    from app.workers.queue import enqueue_deck

    client = TestClient(app)
    # Create session, approved style_bible, then deck (so we have deck + 2 cards for speed)
    r0 = client.post("/style-bible", json={"creative_direction": "x", "medium": "y", "deck_size": 22})
    assert r0.status_code == 202
    session_id = r0.json()["session_id"]
    style_bible_id = r0.json()["style_bible_id"]
    db = SessionLocal()
    sb = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    sb.status = "approved"
    sb.content = "# Style Bible\n\n## Palette\nDark."
    db.commit()
    db.close()
    r1 = client.post(f"/sessions/{session_id}/decks", json={"style_bible_id": style_bible_id, "deck_size": 22})
    assert r1.status_code == 201
    deck_id = r1.json()["id"]
    db = SessionLocal()
    job = get_next_deck_job(db)
    assert job is not None
    payload = json.loads(job.payload)
    assert payload.get("deck_id") == deck_id
    # Mock run_concept_crew and generate_and_save_image so no LLM/API calls
    def mock_run(*, style_bible: str, card_name: str, card_index: int):
        return CardConcept(
            name=card_name,
            meaning=f"Meaning of {card_name}",
            description=f"Description for {card_name}",
            image_prompt=f"Image prompt for {card_name}",
        )
    def mock_image_gen(prompt, *, deck_id, card_id):
        return f"decks/{deck_id}/{card_id}.png", "image/png"
    def mock_evaluator(*, style_bible, concept, image_path):
        return ApproveReject(decision="APPROVE", feedback=None)
    with patch("app.workers.deck_worker.run_concept_crew", side_effect=mock_run), patch(
        "app.workers.deck_worker.generate_and_save_image", side_effect=mock_image_gen
    ), patch("app.workers.deck_worker.run_evaluator", side_effect=mock_evaluator):
        process_deck_job(db, job)
    db.refresh(job)
    assert job.status == "complete"
    cards = db.query(models.Card).filter(models.Card.deck_id == deck_id).order_by(models.Card.position).all()
    assert len(cards) == 22
    assert cards[0].status == "approved"
    assert cards[0].meaning == "Meaning of The Fool"
    assert cards[0].image_prompt == "Image prompt for The Fool"
    asset = db.query(models.Asset).filter(models.Asset.card_id == cards[0].id, models.Asset.kind == "image").first()
    assert asset is not None
    assert asset.storage_path == f"decks/{deck_id}/{cards[0].id}.png"
    db.close()


def test_process_deck_job_retry_loop_reject_then_approve():
    """Evaluator REJECT then refiner + image_gen + evaluator APPROVE leaves card approved with retry_count=1."""
    from fastapi.testclient import TestClient

    from app import models
    from app.main import app
    from tests.shared_db import SessionLocal
    from app.workers.deck_worker import get_next_deck_job, process_deck_job

    client = TestClient(app)
    r0 = client.post("/style-bible", json={"creative_direction": "x", "medium": "y", "deck_size": 22})
    assert r0.status_code == 202
    session_id = r0.json()["session_id"]
    style_bible_id = r0.json()["style_bible_id"]
    db = SessionLocal()
    sb = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    sb.status = "approved"
    sb.content = "# Bible"
    db.commit()
    db.close()
    r1 = client.post(f"/sessions/{session_id}/decks", json={"style_bible_id": style_bible_id, "deck_size": 22})
    assert r1.status_code == 201
    deck_id = r1.json()["id"]
    db = SessionLocal()
    job = get_next_deck_job(db)
    assert job is not None
    # First card: REJECT then APPROVE (retry loop). Other 21 cards: APPROVE once each.
    eval_results = [
        ApproveReject(decision="REJECT", feedback="Add more contrast."),
        ApproveReject(decision="APPROVE", feedback=None),
    ] + [ApproveReject(decision="APPROVE", feedback=None)] * 21
    def mock_run_concept(*, style_bible, card_name, card_index):
        return CardConcept(name=card_name, meaning="M", description="D", image_prompt="P")
    def mock_image_gen(prompt, *, deck_id, card_id):
        return f"decks/{deck_id}/{card_id}.png", "image/png"
    def mock_evaluator(*, style_bible, concept, image_path):
        return eval_results.pop(0)
    def mock_refiner(*, current_image_prompt, evaluator_feedback, style_bible):
        return RefinedPrompt(image_prompt=current_image_prompt + " High contrast.", description=None)
    with patch("app.workers.deck_worker.run_concept_crew", side_effect=mock_run_concept), patch(
        "app.workers.deck_worker.generate_and_save_image", side_effect=mock_image_gen
    ), patch("app.workers.deck_worker.run_evaluator", side_effect=mock_evaluator), patch(
        "app.workers.deck_worker.run_refiner", side_effect=mock_refiner
    ):
        process_deck_job(db, job)
    db.refresh(job)
    assert job.status == "complete"
    cards = db.query(models.Card).filter(models.Card.deck_id == deck_id).order_by(models.Card.position).all()
    assert cards[0].status == "approved"
    assert cards[0].retry_count == 1
    db.close()
