"""Process deck jobs: run concept crew per card, update card rows."""

import json
import logging

from sqlalchemy.orm import Session

from app.crews.concept_crew import run_concept_crew
from app.models import Asset, Card, Deck, Job, StyleBible
from app.services.image_gen import generate_and_save_image
from app.workers.queue import DECK_JOB_TYPE

logger = logging.getLogger(__name__)


def get_next_deck_job(db: Session) -> Job | None:
    """Return one pending deck job or None."""
    return (
        db.query(Job)
        .filter(Job.type == DECK_JOB_TYPE, Job.status == "pending")
        .order_by(Job.created_at)
        .first()
    )


def process_deck_job(db: Session, job: Job) -> None:
    """
    Run concept crew for each card in the deck and update card rows (name, meaning, description, image_prompt, status=concept).
    Sets deck.status to generating; on success marks job complete.
    """
    payload = json.loads(job.payload or "{}")
    deck_id = payload.get("deck_id")
    if not deck_id:
        job.status = "failed"
        db.commit()
        raise ValueError("Job payload missing deck_id")

    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        job.status = "failed"
        db.commit()
        raise ValueError(f"Deck {deck_id} not found")

    style_bible = db.query(StyleBible).filter(StyleBible.id == deck.style_bible_id).first()
    if not style_bible or not style_bible.content:
        job.status = "failed"
        db.commit()
        raise ValueError("Style bible content missing for deck")

    deck.status = "generating"
    db.commit()

    try:
        cards = db.query(Card).filter(Card.deck_id == deck_id).order_by(Card.position).all()
        for card in cards:
            concept = run_concept_crew(
                style_bible=style_bible.content,
                card_name=card.name or "",
                card_index=card.position,
            )
            card.name = concept.name
            card.meaning = concept.meaning
            card.description = concept.description
            card.image_prompt = concept.image_prompt
            card.status = "concept"
            db.commit()
            logger.info("Concept crew completed for card %s (deck %s)", card.id, deck_id)
            # Generate image and store asset
            try:
                storage_path, content_type = generate_and_save_image(
                    concept.image_prompt,
                    deck_id=deck_id,
                    card_id=card.id,
                )
                asset = Asset(
                    card_id=card.id,
                    deck_id=deck_id,
                    kind="image",
                    storage_path=storage_path,
                    content_type=content_type,
                )
                db.add(asset)
                card.status = "image"
                db.commit()
                logger.info("Image generated for card %s (deck %s)", card.id, deck_id)
            except Exception as img_err:
                logger.exception("Image generation failed for card %s: %s", card.id, img_err)
                card.status = "concept"
                db.commit()
                raise
        job.status = "complete"
        db.commit()
    except Exception as e:
        logger.exception("Deck job %s failed: %s", job.id, e)
        job.status = "failed"
        db.commit()
        raise
