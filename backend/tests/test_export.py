"""Tests for deck export (zip, PDF) and download API."""

import base64
import os
import zipfile

from fastapi.testclient import TestClient

from app import models
from app.main import app
from app.services.export import build_pdf, build_zip
from tests.shared_db import SessionLocal

client = TestClient(app)

# Minimal 1x1 PNG (valid PNG bytes)
_MINIMAL_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def _write_minimal_png(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(base64.b64decode(_MINIMAL_PNG_B64))


def _storage_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "uploads"))


def test_build_zip_produces_zip_with_images_and_metadata(monkeypatch):
    storage_dir = _storage_dir()
    monkeypatch.setenv("IMAGE_STORAGE_DIR", storage_dir)
    r0 = client.post(
        "/style-bible",
        json={"creative_direction": "g", "medium": "m", "deck_size": 22},
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
    cards = db.query(models.Card).filter(models.Card.deck_id == deck_id).order_by(models.Card.position).limit(2).all()
    for card in cards:
        rel_path = f"decks/{deck_id}/{card.id}.png"
        abs_path = os.path.join(storage_dir, rel_path)
        _write_minimal_png(abs_path)
        db.add(models.Asset(
            card_id=card.id,
            deck_id=deck_id,
            kind="image",
            storage_path=rel_path,
            content_type="image/png",
        ))
    db.commit()
    db.close()

    db = SessionLocal()
    build_zip(deck_id, db)
    db.close()

    zip_path = os.path.join(storage_dir, "decks", deck_id, "deck.zip")
    assert os.path.isfile(zip_path), zip_path
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
    assert "metadata.json" in names
    image_entries = [n for n in names if n.endswith(".png")]
    assert len(image_entries) >= 2


def test_build_pdf_produces_pdf(monkeypatch):
    storage_dir = _storage_dir()
    monkeypatch.setenv("IMAGE_STORAGE_DIR", storage_dir)
    r0 = client.post("/style-bible", json={"creative_direction": "x", "medium": "y", "deck_size": 22})
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
    card = db.query(models.Card).filter(models.Card.deck_id == deck_id).order_by(models.Card.position).first()
    rel_path = f"decks/{deck_id}/{card.id}.png"
    _write_minimal_png(os.path.join(storage_dir, rel_path))
    db.add(models.Asset(card_id=card.id, deck_id=deck_id, kind="image", storage_path=rel_path, content_type="image/png"))
    db.commit()
    db.close()

    db = SessionLocal()
    build_pdf(deck_id, db)
    db.close()

    pdf_path = os.path.join(storage_dir, "decks", deck_id, "deck.pdf")
    assert os.path.isfile(pdf_path)
    with open(pdf_path, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_download_returns_400_for_invalid_type():
    r0 = client.post("/style-bible", json={"creative_direction": "x", "medium": "y", "deck_size": 22})
    db = SessionLocal()
    db.query(models.StyleBible).filter(models.StyleBible.id == r0.json()["style_bible_id"]).update({"status": "approved"})
    db.commit()
    db.close()
    r = client.post(
        f"/sessions/{r0.json()['session_id']}/decks",
        json={"style_bible_id": r0.json()["style_bible_id"], "deck_size": 22},
    )
    deck_id = r.json()["id"]
    r2 = client.get(f"/decks/{deck_id}/download?type=exe")
    assert r2.status_code == 400


def test_download_returns_404_when_export_not_found():
    r0 = client.post("/style-bible", json={"creative_direction": "x", "medium": "y", "deck_size": 22})
    db = SessionLocal()
    db.query(models.StyleBible).filter(models.StyleBible.id == r0.json()["style_bible_id"]).update({"status": "approved"})
    db.commit()
    db.close()
    r = client.post(
        f"/sessions/{r0.json()['session_id']}/decks",
        json={"style_bible_id": r0.json()["style_bible_id"], "deck_size": 22},
    )
    deck_id = r.json()["id"]
    r2 = client.get(f"/decks/{deck_id}/download?type=zip")
    assert r2.status_code == 404


def test_download_returns_200_with_file_when_zip_built(monkeypatch):
    storage_dir = _storage_dir()
    monkeypatch.setenv("IMAGE_STORAGE_DIR", storage_dir)
    r0 = client.post("/style-bible", json={"creative_direction": "x", "medium": "y", "deck_size": 22})
    db = SessionLocal()
    db.query(models.StyleBible).filter(models.StyleBible.id == r0.json()["style_bible_id"]).update({"status": "approved"})
    db.commit()
    db.close()
    r = client.post(
        f"/sessions/{r0.json()['session_id']}/decks",
        json={"style_bible_id": r0.json()["style_bible_id"], "deck_size": 22},
    )
    deck_id = r.json()["id"]
    db = SessionLocal()
    card = db.query(models.Card).filter(models.Card.deck_id == deck_id).first()
    rel_path = f"decks/{deck_id}/{card.id}.png"
    _write_minimal_png(os.path.join(storage_dir, rel_path))
    db.add(models.Asset(card_id=card.id, deck_id=deck_id, kind="image", storage_path=rel_path, content_type="image/png"))
    db.commit()
    db.close()
    db = SessionLocal()
    build_zip(deck_id, db)
    db.close()
    r2 = client.get(f"/decks/{deck_id}/download?type=zip")
    assert r2.status_code == 200
    assert r2.headers.get("content-type", "").startswith("application/zip")
    assert b"PK" == r2.content[:2]
