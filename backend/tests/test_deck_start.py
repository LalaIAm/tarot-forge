"""Deck creation and job enqueue: only when style bible is approved."""

from fastapi.testclient import TestClient

from app import models
from app.main import app
from tests.shared_db import SessionLocal

client = TestClient(app)


def test_create_deck_with_approved_style_bible_returns_201_and_creates_cards():
    # Create session + style_bible via POST style-bible
    r0 = client.post(
        "/style-bible",
        json={"creative_direction": "gothic", "medium": "ink", "deck_size": 78},
    )
    assert r0.status_code == 202
    session_id = r0.json()["session_id"]
    style_bible_id = r0.json()["style_bible_id"]
    # Set style_bible to approved
    db = SessionLocal()
    sb = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    sb.status = "approved"
    sb.content = "# Bible"
    db.commit()
    db.close()
    # POST create deck (78 cards)
    r = client.post(
        f"/sessions/{session_id}/decks",
        json={"style_bible_id": style_bible_id, "deck_size": 78},
    )
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["session_id"] == session_id
    assert data["style_bible_id"] == style_bible_id
    assert data["deck_size"] == 78
    assert data["status"] == "pending"
    deck_id = data["id"]
    db = SessionLocal()
    cards = db.query(models.Card).filter(models.Card.deck_id == deck_id).order_by(models.Card.position).all()
    assert len(cards) == 78
    assert cards[0].position == 0
    assert cards[0].name == "The Fool"
    assert cards[0].status == "pending"
    assert cards[21].name == "The World"
    job = db.query(models.Job).filter(models.Job.type == "deck").order_by(models.Job.created_at.desc()).first()
    assert job is not None
    import json as _json
    assert _json.loads(job.payload).get("deck_id") == deck_id
    db.close()


def test_create_deck_22_cards():
    r0 = client.post(
        "/style-bible",
        json={"creative_direction": "x", "medium": "y", "deck_size": 22},
    )
    assert r0.status_code == 202
    session_id = r0.json()["session_id"]
    style_bible_id = r0.json()["style_bible_id"]
    db = SessionLocal()
    db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).update({"status": "approved"})
    db.commit()
    db.close()
    r = client.post(
        f"/sessions/{session_id}/decks",
        json={"style_bible_id": style_bible_id, "deck_size": 22},
    )
    assert r.status_code == 201
    deck_id = r.json()["id"]
    db = SessionLocal()
    cards = db.query(models.Card).filter(models.Card.deck_id == deck_id).all()
    assert len(cards) == 22
    assert cards[0].name == "The Fool"
    assert cards[21].name == "The World"
    db.close()


def test_create_deck_rejects_non_approved_style_bible_400():
    r0 = client.post(
        "/style-bible",
        json={"creative_direction": "x", "medium": "y", "deck_size": 78},
    )
    assert r0.status_code == 202
    session_id = r0.json()["session_id"]
    style_bible_id = r0.json()["style_bible_id"]
    # Leave status as "generating" (or "ready" but not "approved")
    r = client.post(
        f"/sessions/{session_id}/decks",
        json={"style_bible_id": style_bible_id, "deck_size": 78},
    )
    assert r.status_code == 400
    assert "approved" in r.json().get("detail", "").lower()


def test_create_deck_404_unknown_session():
    r0 = client.post("/style-bible", json={"creative_direction": "x", "medium": "y", "deck_size": 78})
    style_bible_id = r0.json()["style_bible_id"]
    db = SessionLocal()
    db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).update({"status": "approved"})
    db.commit()
    db.close()
    r = client.post(
        "/sessions/00000000-0000-0000-0000-000000000000/decks",
        json={"style_bible_id": style_bible_id, "deck_size": 78},
    )
    assert r.status_code == 404


def test_create_deck_404_unknown_style_bible():
    r0 = client.post("/sessions")
    assert r0.status_code == 201
    session_id = r0.json()["id"]
    r = client.post(
        f"/sessions/{session_id}/decks",
        json={"style_bible_id": "00000000-0000-0000-0000-000000000000", "deck_size": 78},
    )
    assert r.status_code == 404
