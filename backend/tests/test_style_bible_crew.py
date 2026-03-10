"""Tests for style-bible crew and worker. Mocks LLM so no API key required."""

from unittest.mock import patch

from crewai import Process

from app.crews.outputs import StyleBibleOutput
from app.crews.style_bible_crew import build_style_bible_crew
from app.models import Job
from app.workers.style_bible_worker import process_style_bible_job


def test_build_style_bible_crew_has_three_agents_and_three_tasks():
    crew = build_style_bible_crew()
    assert len(crew.agents) == 3
    assert len(crew.tasks) == 3
    assert crew.process == Process.sequential


def test_style_bible_output_to_markdown():
    out = StyleBibleOutput(
        palette="Earth tones and gold accents",
        typography="Serif for titles",
        symbolism="Classical tarot symbols",
        layout="Centered figure, ornate border",
        tone="Mysterious and elegant",
    )
    md = out.to_markdown()
    assert "# Style Bible" in md
    assert "## Palette" in md
    assert "Earth tones and gold accents" in md
    assert "## Typography" in md
    assert "## Symbolism" in md
    assert "## Layout" in md
    assert "## Tone" in md


def test_process_style_bible_job_updates_db():
    from fastapi.testclient import TestClient

    from app import models
    from app.main import app
    from tests.shared_db import SessionLocal

    client = TestClient(app)

    # Enqueue a job (creates session + style_bible + job)
    r = client.post(
        "/style-bible",
        json={
            "creative_direction": "dark botanical",
            "medium": "watercolor",
            "deck_size": 78,
        },
    )
    assert r.status_code == 202
    style_bible_id = r.json()["style_bible_id"]

    import json as _json

    db = SessionLocal()
    # Get the job for this test's style_bible (shared DB may have other pending jobs)
    all_jobs = db.query(Job).filter(Job.type == "style_bible", Job.status == "pending").all()
    job = next(
        (j for j in all_jobs if _json.loads(j.payload).get("style_bible_id") == style_bible_id),
        None,
    )
    assert job is not None

    mock_output = StyleBibleOutput(
        palette="Dark greens and black",
        typography="Hand-lettered",
        symbolism="Botanical motifs",
        layout="Full bleed",
        tone="Moody",
    )

    with patch("app.workers.style_bible_worker.run_style_bible_crew", return_value=mock_output):
        process_style_bible_job(db, job)

    db.refresh(job)
    style_bible = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    assert style_bible.status == "ready"
    assert style_bible.content is not None
    assert "## Palette" in style_bible.content
    assert "Dark greens and black" in style_bible.content
    assert job.status == "complete"
    db.close()
