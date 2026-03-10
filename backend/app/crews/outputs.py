"""Pydantic models for CrewAI task outputs. Used with output_pydantic on tasks."""

from pydantic import BaseModel, Field


class StyleBibleOutput(BaseModel):
    """Structured style bible produced by the Designer agent."""

    palette: str = Field(..., description="Color palette and usage guidelines")
    typography: str = Field(..., description="Typefaces and typographic rules")
    symbolism: str = Field(..., description="Symbolic and thematic guidelines")
    layout: str = Field(..., description="Card layout and composition rules")
    tone: str = Field(..., description="Overall tone and mood")

    def to_markdown(self) -> str:
        return f"""# Style Bible

## Palette
{self.palette}

## Typography
{self.typography}

## Symbolism
{self.symbolism}

## Layout
{self.layout}

## Tone
{self.tone}
"""
