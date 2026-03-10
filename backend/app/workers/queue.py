import json
from typing import Any

from sqlalchemy.orm import Session

from app.data.tarot_cards import card_name_for_position
from app.models import Card, Deck, Job, Session as SessionModel, StyleBible

STYLE_BIBLE_JOB_TYPE = "style_bible"
DECK_JOB_TYPE = "deck"
VALID_DECK_SIZES = (22, 78)


def enqueue_style_bible(
    db: Session,
    *,
    session_id: str | None = None,
    creative_direction: str,
    medium: str,
    deck_size: int = 78,
) -> tuple[str, str]:
    """
    Create or use session, create style_bible (status=generating), enqueue job.
    Returns (session_id, style_bible_id).
    """
    if session_id:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise ValueError("Session not found")
    else:
        session = SessionModel()
        db.add(session)
        db.flush()

    style_bible = StyleBible(
        session_id=session.id,
        status="generating",
        content=None,
        revision=0,
        creative_direction=creative_direction,
        medium=medium,
        deck_size=deck_size,
    )
    db.add(style_bible)
    db.flush()

    payload: dict[str, Any] = {
        "session_id": session.id,
        "style_bible_id": style_bible.id,
        "creative_direction": creative_direction,
        "medium": medium,
        "deck_size": deck_size,
    }
    job = Job(
        type=STYLE_BIBLE_JOB_TYPE,
        payload=json.dumps(payload),
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(style_bible)
    return session.id, style_bible.id


def enqueue_style_bible_request_changes(
    db: Session,
    *,
    style_bible_id: str,
    feedback: str,
) -> str:
    """
    Update same style_bibles row: bump revision, set status=generating, enqueue job.
    Style bible must be in status 'ready'. Returns style_bible_id.
    """
    style_bible = db.query(StyleBible).filter(StyleBible.id == style_bible_id).first()
    if not style_bible:
        raise ValueError("Style bible not found")
    if style_bible.status != "ready":
        raise ValueError("Style bible must be ready to request changes")
    style_bible.revision += 1
    style_bible.status = "generating"
    payload: dict[str, Any] = {
        "style_bible_id": style_bible_id,
        "feedback": feedback,
    }
    job = Job(
        type=STYLE_BIBLE_JOB_TYPE,
        payload=json.dumps(payload),
        status="pending",
    )
    db.add(job)
    db.commit()
    return style_bible_id


def enqueue_deck(
    db: Session,
    *,
    session_id: str,
    style_bible_id: str,
    deck_size: int,
) -> str:
    """
    Create deck and N card rows (status pending), enqueue deck job.
    Style bible must be in status 'approved'. Returns deck_id.
    """
    if deck_size not in VALID_DECK_SIZES:
        raise ValueError("deck_size must be 22 or 78")
    style_bible = db.query(StyleBible).filter(StyleBible.id == style_bible_id).first()
    if not style_bible:
        raise ValueError("Style bible not found")
    if style_bible.status != "approved":
        raise ValueError("Style bible must be approved to start deck generation")
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise ValueError("Session not found")
    deck = Deck(
        session_id=session_id,
        style_bible_id=style_bible_id,
        status="pending",
        deck_size=deck_size,
    )
    db.add(deck)
    db.flush()
    for pos in range(deck_size):
        name = card_name_for_position(pos, deck_size)
        card = Card(
            deck_id=deck.id,
            position=pos,
            name=name,
            status="pending",
        )
        db.add(card)
    payload: dict[str, Any] = {"deck_id": deck.id}
    job = Job(
        type=DECK_JOB_TYPE,
        payload=json.dumps(payload),
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(deck)
    return deck.id
