"""Pydantic models for CrewAI task outputs. Used with output_pydantic on tasks."""

from typing import Literal

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


class MeaningDescription(BaseModel):
    """Tarot Scholar output: meaning and description for a card."""

    meaning: str = Field(..., description="Tarot meaning and symbolism")
    description: str = Field(..., description="Short narrative description for the card")


class ImagePromptOutput(BaseModel):
    """Visual Designer output: image prompt for one card."""

    image_prompt: str = Field(..., description="Prompt for image generation matching style bible")


class CardConcept(BaseModel):
    """Per-card concept from Tarot Scholar + Visual Designer: name, meaning, description, image_prompt."""

    name: str = Field(..., description="Card name (e.g. The Fool)")
    meaning: str = Field(..., description="Tarot meaning and symbolism")
    description: str = Field(..., description="Short narrative description for the card")
    image_prompt: str = Field(..., description="Prompt for image generation matching style bible")


class ApproveReject(BaseModel):
    """Evaluator output: approve or reject the card image, with optional feedback for reprompting."""

    decision: Literal["APPROVE", "REJECT"] = Field(..., description="APPROVE or REJECT")
    feedback: str | None = Field(None, description="If REJECT, short reprompting feedback for the refiner")


class RefinedPrompt(BaseModel):
    """Refiner output: updated image prompt and optional description after evaluator feedback."""

    image_prompt: str = Field(..., description="Updated image prompt incorporating feedback")
    description: str | None = Field(None, description="Optional updated card description")
