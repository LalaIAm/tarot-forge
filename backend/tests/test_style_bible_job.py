# Same DB override pattern as test_sessions_api: in-memory + StaticPool
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app import models  # noqa: F401
from app.main import app

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


def test_post_style_bible_creates_session_and_returns_202():
    r = client.post(
        "/style-bible",
        json={
            "creative_direction": "dark botanical art nouveau",
            "medium": "watercolor",
            "deck_size": 78,
        },
    )
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "generating"
    assert "session_id" in data
    assert "style_bible_id" in data
    assert len(data["session_id"]) == 36
    assert len(data["style_bible_id"]) == 36


def test_post_style_bible_to_existing_session_returns_202():
    # Create session first
    r0 = client.post("/sessions")
    assert r0.status_code == 201
    session_id = r0.json()["id"]
    r = client.post(
        f"/sessions/{session_id}/style-bible",
        json={
            "creative_direction": "minimal line art",
            "medium": "digital",
            "deck_size": 22,
        },
    )
    assert r.status_code == 202
    data = r.json()
    assert data["session_id"] == session_id
    assert data["status"] == "generating"
    assert "style_bible_id" in data


def test_post_style_bible_unknown_session_404():
    r = client.post(
        "/sessions/00000000-0000-0000-0000-000000000000/style-bible",
        json={
            "creative_direction": "gothic",
            "medium": "ink",
            "deck_size": 78,
        },
    )
    assert r.status_code == 404


def test_post_style_bible_invalid_deck_size_422():
    r = client.post(
        "/style-bible",
        json={
            "creative_direction": "gothic",
            "medium": "ink",
            "deck_size": 42,
        },
    )
    assert r.status_code == 422
