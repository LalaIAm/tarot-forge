"""Build deck export: zip of card images + metadata, and print-ready PDF (9-up)."""

import json
import logging
import os
import zipfile

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import Asset, Card, Deck

logger = logging.getLogger(__name__)

# 9-up: 3 columns x 3 rows per page
GRID_COLS = 3
GRID_ROWS = 3
CARDS_PER_PAGE = GRID_COLS * GRID_ROWS
# Cell size in points (letter is 612 x 792)
CELL_W = 612 / GRID_COLS
CELL_H = 792 / GRID_ROWS
MARGIN = 12


def _cards_with_image_assets(db: Session, deck_id: str) -> list[tuple[Card, Asset]]:
    """Return (card, image_asset) for each card that has an image, in position order."""
    deck = (
        db.query(Deck)
        .options(selectinload(Deck.cards).selectinload(Card.assets))
        .filter(Deck.id == deck_id)
        .first()
    )
    if not deck:
        return []
    out = []
    for card in sorted(deck.cards, key=lambda c: c.position):
        for a in card.assets:
            if a.kind == "image":
                out.append((card, a))
                break
    return out


def build_zip(deck_id: str, db: Session) -> str:
    """
    Build a zip of card images (by position) and metadata.json. Save under
    storage_dir/decks/{deck_id}/deck.zip. Create Asset(deck_id, kind=zip).
    Return storage_path (relative).
    """
    settings = get_settings()
    storage_dir = getattr(settings, "image_storage_dir", "uploads")
    deck_dir = os.path.join(storage_dir, "decks", deck_id)
    os.makedirs(deck_dir, exist_ok=True)
    zip_path = os.path.join(deck_dir, "deck.zip")
    storage_path = f"decks/{deck_id}/deck.zip"

    pairs = _cards_with_image_assets(db, deck_id)
    metadata = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for card, asset in pairs:
            abs_path = os.path.join(storage_dir, asset.storage_path)
            if os.path.isfile(abs_path):
                # Safe filename: position and slugged name
                safe_name = (card.name or f"card-{card.position}").replace(" ", "-").replace("/", "-")[:40]
                arcname = f"{card.position:02d}-{safe_name}.png"
                zf.write(abs_path, arcname)
            metadata.append({
                "position": card.position,
                "name": card.name,
                "meaning": card.meaning,
                "description": card.description,
            })
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))

    # Upsert deck-level zip asset
    existing = db.query(Asset).filter(Asset.deck_id == deck_id, Asset.kind == "zip").first()
    if existing:
        existing.storage_path = storage_path
        existing.content_type = "application/zip"
    else:
        db.add(Asset(
            deck_id=deck_id,
            card_id=None,
            kind="zip",
            storage_path=storage_path,
            content_type="application/zip",
        ))
    db.commit()
    return storage_path


def build_pdf(deck_id: str, db: Session) -> str:
    """
    Build a 9-up print-ready PDF of card images. Save under
    storage_dir/decks/{deck_id}/deck.pdf. Create Asset(deck_id, kind=pdf).
    Return storage_path (relative).
    """
    settings = get_settings()
    storage_dir = getattr(settings, "image_storage_dir", "uploads")
    deck_dir = os.path.join(storage_dir, "decks", deck_id)
    os.makedirs(deck_dir, exist_ok=True)
    pdf_path = os.path.join(deck_dir, "deck.pdf")
    storage_path = f"decks/{deck_id}/deck.pdf"

    pairs = _cards_with_image_assets(db, deck_id)
    if not pairs:
        logger.warning("No card images for deck %s; creating empty PDF", deck_id)

    c = canvas.Canvas(pdf_path, pagesize=letter)
    page_cards = 0
    for idx, (card, asset) in enumerate(pairs):
        if page_cards == 0:
            c.setPageSize(letter)
        row = (page_cards // GRID_COLS) % GRID_ROWS
        col = page_cards % GRID_COLS
        x = MARGIN + col * CELL_W
        y = 792 - MARGIN - (row + 1) * CELL_H  # origin bottom-left
        abs_path = os.path.join(storage_dir, asset.storage_path)
        if os.path.isfile(abs_path):
            try:
                c.drawImage(abs_path, x, y, width=CELL_W - 4, height=CELL_H - 4)
            except Exception as e:
                logger.warning("Could not draw image %s: %s", abs_path, e)
        page_cards += 1
        if page_cards == CARDS_PER_PAGE:
            c.showPage()
            page_cards = 0
    if page_cards > 0:
        c.showPage()
    c.save()

    existing = db.query(Asset).filter(Asset.deck_id == deck_id, Asset.kind == "pdf").first()
    if existing:
        existing.storage_path = storage_path
        existing.content_type = "application/pdf"
    else:
        db.add(Asset(
            deck_id=deck_id,
            card_id=None,
            kind="pdf",
            storage_path=storage_path,
            content_type="application/pdf",
        ))
    db.commit()
    return storage_path


def build_exports(deck_id: str, db: Session) -> None:
    """Build zip and PDF for the deck and create/update deck-level assets."""
    try:
        build_zip(deck_id, db)
        logger.info("Zip export built for deck %s", deck_id)
    except Exception as e:
        logger.exception("Zip export failed for deck %s: %s", deck_id, e)
    try:
        build_pdf(deck_id, db)
        logger.info("PDF export built for deck %s", deck_id)
    except Exception as e:
        logger.exception("PDF export failed for deck %s: %s", deck_id, e)
