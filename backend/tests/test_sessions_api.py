# Use override so we control the DB: in-memory + StaticPool so request thread sees same DB as init
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


def test_create_session_returns_201_and_id():
    r = client.post("/sessions")
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert len(data["id"]) == 36
    assert "created_at" in data


def test_get_session_returns_same_session():
    r = client.post("/sessions")
    assert r.status_code == 201
    session_id = r.json()["id"]
    r2 = client.get(f"/sessions/{session_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == session_id


def test_get_session_404_for_unknown_id():
    r = client.get("/sessions/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
