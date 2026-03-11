from fastapi.testclient import TestClient

from app.main import app

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
