from pydantic import BaseModel, ConfigDict, Field, field_validator


class StyleBibleSubmit(BaseModel):
    creative_direction: str = Field(..., min_length=1, max_length=10_000)
    medium: str = Field(..., min_length=1, max_length=500)
    deck_size: int = Field(78, description="78 (full deck) or 22 (Major Arcana only)")

    model_config = ConfigDict(
        json_schema_extra={"example": {"creative_direction": "dark botanical art nouveau", "medium": "watercolor", "deck_size": 78}}
    )

    @field_validator("deck_size")
    @classmethod
    def deck_size_22_or_78(cls, v: int) -> int:
        if v not in (22, 78):
            raise ValueError("deck_size must be 22 or 78")
        return v


class StyleBibleJobOut(BaseModel):
    session_id: str
    style_bible_id: str
    status: str = "generating"
