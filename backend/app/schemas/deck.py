from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeckCreate(BaseModel):
    style_bible_id: str
    deck_size: int = Field(78, description="22 (Major Arcana only) or 78 (full deck)")

    @field_validator("deck_size")
    @classmethod
    def deck_size_22_or_78(cls, v: int) -> int:
        if v not in (22, 78):
            raise ValueError("deck_size must be 22 or 78")
        return v


class DeckOut(BaseModel):
    id: str
    session_id: str
    style_bible_id: str
    status: str
    deck_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
