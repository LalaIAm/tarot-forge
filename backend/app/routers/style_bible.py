from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.style_bible import StyleBibleJobOut, StyleBibleSubmit
from app.workers.queue import enqueue_style_bible

router = APIRouter(tags=["style_bible"])


@router.post("/sessions/{session_id}/style-bible", response_model=StyleBibleJobOut, status_code=202)
def submit_style_bible_job(
    session_id: str,
    body: StyleBibleSubmit,
    db: Session = Depends(get_db),
):
    """Submit creative direction and medium; enqueue style-bible job. Returns session and style_bible ids."""
    try:
        sid, sbid = enqueue_style_bible(
            db,
            session_id=session_id,
            creative_direction=body.creative_direction,
            medium=body.medium,
            deck_size=body.deck_size,
        )
    except ValueError as e:
        if "Session not found" in str(e):
            raise HTTPException(status_code=404, detail="Session not found") from e
        raise
    return StyleBibleJobOut(session_id=sid, style_bible_id=sbid, status="generating")


@router.post("/style-bible", response_model=StyleBibleJobOut, status_code=202)
def submit_style_bible_job_new_session(
    body: StyleBibleSubmit,
    db: Session = Depends(get_db),
):
    """Create a new session and enqueue style-bible job. Returns session and style_bible ids."""
    sid, sbid = enqueue_style_bible(
        db,
        session_id=None,
        creative_direction=body.creative_direction,
        medium=body.medium,
        deck_size=body.deck_size,
    )
    return StyleBibleJobOut(session_id=sid, style_bible_id=sbid, status="generating")
