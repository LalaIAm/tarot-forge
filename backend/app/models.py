import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Integer
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def uuid4_str():
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=uuid4_str)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id: Mapped[Optional[str]] = mapped_column(CHAR(36), nullable=True)

    style_bibles = relationship("StyleBible", back_populates="session")
    decks = relationship("Deck", back_populates="session")


class StyleBible(Base):
    __tablename__ = "style_bibles"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=uuid4_str)
    session_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("sessions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Stored so request-changes can re-run crew without creating a new row
    creative_direction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medium: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    deck_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    session = relationship("Session", back_populates="style_bibles")
    decks = relationship("Deck", back_populates="style_bible")


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=uuid4_str)
    session_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("sessions.id"), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(CHAR(36), nullable=True)
    style_bible_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("style_bibles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    deck_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    session = relationship("Session", back_populates="decks")
    style_bible = relationship("StyleBible", back_populates="decks")
    cards = relationship("Card", back_populates="deck", order_by="Card.position")
    assets = relationship("Asset", back_populates="deck", foreign_keys="Asset.deck_id")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=uuid4_str)
    deck_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("decks.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    meaning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evaluation_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    deck = relationship("Deck", back_populates="cards")
    assets = relationship("Asset", back_populates="card", foreign_keys="Asset.card_id")

    __table_args__ = (Index("ix_cards_deck_id", "deck_id"),)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=uuid4_str)
    card_id: Mapped[Optional[str]] = mapped_column(CHAR(36), ForeignKey("cards.id"), nullable=True)
    deck_id: Mapped[Optional[str]] = mapped_column(CHAR(36), ForeignKey("decks.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    card = relationship("Card", back_populates="assets", foreign_keys=[card_id])
    deck = relationship("Deck", back_populates="assets", foreign_keys=[deck_id])

    __table_args__ = (
        Index("ix_assets_card_id", "card_id"),
        Index("ix_assets_deck_id", "deck_id"),
        Index("ix_assets_kind", "kind"),
    )


class Job(Base):
    """DB-backed job queue for style_bible and deck workers."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=uuid4_str)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_jobs_type_status", "type", "status"),)
