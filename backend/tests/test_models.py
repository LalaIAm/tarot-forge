import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app import models  # noqa: F401 - register with Base
from app.models import Session, StyleBible


@pytest.fixture
def db_session():
    """In-memory SQLite session for tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_create_session_and_style_bible(db_session):
    """Creating a Session and a StyleBible linked to it persists and links correctly."""
    session = Session()
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert session.id is not None
    assert len(session.id) == 36
    assert session.created_at is not None
    assert session.user_id is None

    style_bible = StyleBible(session_id=session.id, status="draft", content="# Style guide\nPalette: dark green")
    db_session.add(style_bible)
    db_session.commit()
    db_session.refresh(style_bible)

    assert style_bible.id is not None
    assert style_bible.session_id == session.id
    assert style_bible.status == "draft"
    assert "Palette" in (style_bible.content or "")
    assert style_bible.revision == 0
