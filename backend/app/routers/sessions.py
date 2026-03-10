from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Session as SessionModel
from app.schemas.session import SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=201)
def create_session(db: Session = Depends(get_db)):
    """Create a new session. Returns session id for use in subsequent requests."""
    session = SessionModel()
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionOut(
        id=session.id,
        created_at=session.created_at.isoformat() if session.created_at else "",
    )


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get a session by id. Returns 404 if not found."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut(
        id=session.id,
        created_at=session.created_at.isoformat() if session.created_at else "",
    )
