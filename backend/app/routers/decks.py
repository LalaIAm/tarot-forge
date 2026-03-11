import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import get_db
from app.models import Asset, Card, Deck
from app.schemas.deck import CardGalleryItem, DeckCreate, DeckDetailOut, DeckOut
from app.workers.queue import enqueue_deck

router = APIRouter(tags=["decks"])


@router.post("/sessions/{session_id}/decks", response_model=DeckOut, status_code=201)
def create_deck(
    session_id: str,
    body: DeckCreate,
    db: Session = Depends(get_db),
):
    """
    Create a deck and enqueue deck generation job. Style bible must be approved.
    Creates deck_size card rows (status pending).
    """
    try:
        deck_id = enqueue_deck(
            db,
            session_id=session_id,
            style_bible_id=body.style_bible_id,
            deck_size=body.deck_size,
        )
    except ValueError as e:
        msg = str(e)
        if "Session not found" in msg:
            raise HTTPException(status_code=404, detail="Session not found") from e
        if "Style bible not found" in msg:
            raise HTTPException(status_code=404, detail="Style bible not found") from e
        if "must be approved" in msg:
            raise HTTPException(
                status_code=400,
                detail="Style bible must be approved to start deck generation",
            ) from e
        if "deck_size" in msg:
            raise HTTPException(status_code=400, detail=msg) from e
        raise
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    return deck


@router.get("/decks/{deck_id}", response_model=DeckDetailOut)
def get_deck(
    deck_id: str,
    include: str | None = Query(None, description="Set to 'cards' to include card list with image_url"),
    db: Session = Depends(get_db),
):
    """
    Get deck metadata and progress (approved_count / total_cards).
    Use ?include=cards to include cards array with image_url for gallery.
    """
    deck = (
        db.query(Deck)
        .options(selectinload(Deck.cards).selectinload(Card.assets))
        .filter(Deck.id == deck_id)
        .first()
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    total = len(deck.cards)
    approved_count = sum(1 for c in deck.cards if c.status == "approved")
    include_cards = include == "cards" or deck.status == "complete"
    cards_out = None
    if include_cards and deck.cards:
        cards_out = []
        for card in deck.cards:
            image_url = None
            for a in card.assets:
                if a.kind == "image":
                    image_url = f"/decks/{deck_id}/cards/{card.id}/image"
                    break
            cards_out.append(
                CardGalleryItem(
                    id=card.id,
                    position=card.position,
                    name=card.name,
                    meaning=card.meaning,
                    description=card.description,
                    status=card.status,
                    image_url=image_url,
                )
            )
    return DeckDetailOut(
        id=deck.id,
        session_id=deck.session_id,
        style_bible_id=deck.style_bible_id,
        status=deck.status,
        deck_size=deck.deck_size,
        created_at=deck.created_at,
        approved_count=approved_count,
        total_cards=total,
        cards=cards_out,
    )


DOWNLOAD_TYPES = ("zip", "pdf")


@router.get("/decks/{deck_id}/download")
def download_deck_export(
    deck_id: str,
    export_type: str = Query(..., alias="type", description="Export type: zip or pdf"),
    db: Session = Depends(get_db),
):
    """
    Download deck export (zip or PDF). Resolves asset by deck_id + type only.
    Returns 404 if deck not found or export not yet generated.
    """
    if export_type not in DOWNLOAD_TYPES:
        raise HTTPException(status_code=400, detail="type must be zip or pdf")
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    asset = db.query(Asset).filter(
        Asset.deck_id == deck_id,
        Asset.kind == export_type,
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Export not found")
    settings = get_settings()
    storage_dir = getattr(settings, "image_storage_dir", "uploads")
    abs_path = os.path.join(storage_dir, asset.storage_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="Export file not found")
    media_types = {"zip": "application/zip", "pdf": "application/pdf"}
    filename = f"deck-{deck_id}.{export_type}"
    return FileResponse(
        abs_path,
        media_type=media_types.get(export_type, "application/octet-stream"),
        filename=filename,
    )


@router.get("/decks/{deck_id}/cards/{card_id}/image")
def get_card_image(
    deck_id: str,
    card_id: str,
    db: Session = Depends(get_db),
):
    """Serve the card's image asset from local storage."""
    card = (
        db.query(Card)
        .filter(Card.deck_id == deck_id, Card.id == card_id)
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    asset = db.query(Asset).filter(
        Asset.card_id == card_id,
        Asset.kind == "image",
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Image not found")
    settings = get_settings()
    storage_dir = getattr(settings, "image_storage_dir", "uploads")
    abs_path = os.path.join(storage_dir, asset.storage_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(
        abs_path,
        media_type=asset.content_type or "image/png",
    )