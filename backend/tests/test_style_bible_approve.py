import json as _json

from fastapi.testclient import TestClient

from app import models
from app.main import app
from tests.shared_db import SessionLocal

client = TestClient(app)


def test_get_style_bible_by_session_returns_latest():
    # Create session + style_bible via POST
    r = client.post(
        "/style-bible",
        json={"creative_direction": "gothic", "medium": "ink", "deck_size": 78},
    )
    assert r.status_code == 202
    session_id = r.json()["session_id"]
    style_bible_id = r.json()["style_bible_id"]
    # Set style_bible to ready with content (simulate worker finished)
    db = SessionLocal()
    sb = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    sb.status = "ready"
    sb.content = "# Style Bible\n\n## Palette\nDark."
    db.commit()
    db.close()
    # GET by session
    r2 = client.get(f"/sessions/{session_id}/style-bible")
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == style_bible_id
    assert data["status"] == "ready"
    assert "Palette" in data["content"]


def test_get_style_bible_by_session_404_when_none():
    r = client.post("/sessions")
    assert r.status_code == 201
    session_id = r.json()["id"]
    r2 = client.get(f"/sessions/{session_id}/style-bible")
    assert r2.status_code == 404


def test_get_style_bible_by_id():
    r = client.post(
        "/style-bible",
        json={"creative_direction": "minimal", "medium": "digital", "deck_size": 22},
    )
    assert r.status_code == 202
    style_bible_id = r.json()["style_bible_id"]
    db = SessionLocal()
    sb = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    sb.status = "ready"
    sb.content = "# Bible"
    db.commit()
    db.close()
    r2 = client.get(f"/style-bibles/{style_bible_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == style_bible_id
    assert r2.json()["status"] == "ready"


def test_approve_sets_status_to_approved():
    r = client.post(
        "/style-bible",
        json={"creative_direction": "x", "medium": "y", "deck_size": 78},
    )
    assert r.status_code == 202
    style_bible_id = r.json()["style_bible_id"]
    db = SessionLocal()
    sb = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    sb.status = "ready"
    sb.content = "# Bible"
    db.commit()
    db.close()
    r2 = client.post(f"/style-bibles/{style_bible_id}/approve")
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"
    r3 = client.get(f"/style-bibles/{style_bible_id}")
    assert r3.json()["status"] == "approved"


def test_approve_400_when_not_ready():
    r = client.post(
        "/style-bible",
        json={"creative_direction": "x", "medium": "y", "deck_size": 78},
    )
    assert r.status_code == 202
    style_bible_id = r.json()["style_bible_id"]
    # status is still "generating"
    r2 = client.post(f"/style-bibles/{style_bible_id}/approve")
    assert r2.status_code == 400


def test_request_changes_bumps_revision_and_enqueues_job():
    r = client.post(
        "/style-bible",
        json={"creative_direction": "x", "medium": "y", "deck_size": 78},
    )
    assert r.status_code == 202
    style_bible_id = r.json()["style_bible_id"]
    db = SessionLocal()
    sb = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    sb.status = "ready"
    sb.content = "# Bible"
    sb.revision = 0
    db.commit()
    db.close()
    r2 = client.post(
        f"/style-bibles/{style_bible_id}/request-changes",
        json={"feedback": "More gold accents please"},
    )
    assert r2.status_code == 202
    assert r2.json()["status"] == "generating"
    db = SessionLocal()
    sb = db.query(models.StyleBible).filter(models.StyleBible.id == style_bible_id).first()
    assert sb.revision == 1
    assert sb.status == "generating"
    jobs = db.query(models.Job).filter(
        models.Job.type == "style_bible", models.Job.status == "pending"
    ).all()
    job = next(
        (j for j in jobs if _json.loads(j.payload).get("feedback") == "More gold accents please"),
        None,
    )
    assert job is not None
    payload = _json.loads(job.payload)
    assert payload.get("style_bible_id") == style_bible_id
    assert payload.get("feedback") == "More gold accents please"
    db.close()


def test_request_changes_400_when_not_ready():
    r = client.post(
        "/style-bible",
        json={"creative_direction": "x", "medium": "y", "deck_size": 78},
    )
    assert r.status_code == 202
    style_bible_id = r.json()["style_bible_id"]
    r2 = client.post(
        f"/style-bibles/{style_bible_id}/request-changes",
        json={"feedback": "More gold"},
    )
    assert r2.status_code == 400
