from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import StyleBible
from app.schemas.style_bible import (
    RequestChangesBody,
    StyleBibleJobOut,
    StyleBibleOut,
    StyleBibleSubmit,
)
from app.workers.queue import enqueue_style_bible, enqueue_style_bible_request_changes

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


@router.get("/sessions/{session_id}/style-bible", response_model=StyleBibleOut)
def get_style_bible_by_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Return the latest style bible for this session (by created_at)."""
    style_bible = (
        db.query(StyleBible)
        .filter(StyleBible.session_id == session_id)
        .order_by(StyleBible.created_at.desc())
        .first()
    )
    if not style_bible:
        raise HTTPException(status_code=404, detail="Style bible not found")
    return style_bible


@router.get("/style-bibles/{style_bible_id}", response_model=StyleBibleOut)
def get_style_bible(
    style_bible_id: str,
    db: Session = Depends(get_db),
):
    """Return a style bible by id."""
    style_bible = db.query(StyleBible).filter(StyleBible.id == style_bible_id).first()
    if not style_bible:
        raise HTTPException(status_code=404, detail="Style bible not found")
    return style_bible


@router.post("/style-bibles/{style_bible_id}/approve", response_model=StyleBibleOut)
def approve_style_bible(
    style_bible_id: str,
    db: Session = Depends(get_db),
):
    """Set style bible status to approved. Only valid when status is ready."""
    style_bible = db.query(StyleBible).filter(StyleBible.id == style_bible_id).first()
    if not style_bible:
        raise HTTPException(status_code=404, detail="Style bible not found")
    if style_bible.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve style bible with status {style_bible.status}; must be ready",
        )
    style_bible.status = "approved"
    db.commit()
    db.refresh(style_bible)
    return style_bible


@router.post("/style-bibles/{style_bible_id}/request-changes", status_code=202)
def request_changes_style_bible(
    style_bible_id: str,
    body: RequestChangesBody,
    db: Session = Depends(get_db),
):
    """Bump revision, set status to generating, and enqueue a new job with feedback."""
    try:
        enqueue_style_bible_request_changes(
            db,
            style_bible_id=style_bible_id,
            feedback=body.feedback,
        )
    except ValueError as e:
        if "Style bible not found" in str(e):
            raise HTTPException(status_code=404, detail="Style bible not found") from e
        if "must be ready" in str(e):
            raise HTTPException(
                status_code=400,
                detail="Style bible must be ready to request changes",
            ) from e
        raise
    return {"style_bible_id": style_bible_id, "status": "generating"}
