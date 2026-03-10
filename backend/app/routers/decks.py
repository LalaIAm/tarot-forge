from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Deck
from app.schemas.deck import DeckCreate, DeckOut
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