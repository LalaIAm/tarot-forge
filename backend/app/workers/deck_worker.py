"""Process deck jobs: run concept crew, image gen, and evaluator per card."""

import json
import logging
import os

from sqlalchemy.orm import Session

from app.config import get_settings
from app.crews.concept_crew import run_concept_crew
from app.crews.evaluator_crew import run_evaluator
from app.crews.outputs import CardConcept
from app.crews.refiner_crew import run_refiner
from app.models import Asset, Card, Deck, Job, StyleBible
from app.services.export import build_exports
from app.services.image_gen import generate_and_save_image
from app.workers.queue import DECK_JOB_TYPE

logger = logging.getLogger(__name__)

MAX_EVALUATOR_RETRIES = 3


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
                db.commit()
                card.status = "image"
                db.commit()
                logger.info("Image generated for card %s (deck %s)", card.id, deck_id)
                # Evaluate image; on REJECT, refiner → image_gen → evaluator loop up to MAX_EVALUATOR_RETRIES
                settings = get_settings()
                abs_path = os.path.join(getattr(settings, "image_storage_dir", "uploads"), storage_path)
                concept_for_eval = CardConcept(
                    name=card.name or "",
                    meaning=card.meaning or "",
                    description=card.description or "",
                    image_prompt=card.image_prompt or "",
                )
                try:
                    eval_result = run_evaluator(
                        style_bible=style_bible.content,
                        concept=concept_for_eval,
                        image_path=abs_path,
                    )
                except Exception as eval_err:
                    logger.exception("Evaluator failed for card %s: %s", card.id, eval_err)
                    card.status = "image"
                    db.commit()
                    raise
                card.evaluation_feedback = eval_result.feedback
                if eval_result.decision == "APPROVE":
                    card.status = "approved"
                    db.commit()
                    logger.info("Evaluator APPROVE for card %s (deck %s)", card.id, deck_id)
                else:
                    # Retry loop: refiner → image_gen (overwrite) → evaluator
                    while card.retry_count < MAX_EVALUATOR_RETRIES:
                        refined = run_refiner(
                            current_image_prompt=card.image_prompt or "",
                            evaluator_feedback=eval_result.feedback or "Image did not match style or concept.",
                            style_bible=style_bible.content,
                        )
                        card.image_prompt = refined.image_prompt
                        if refined.description is not None:
                            card.description = refined.description
                        card.retry_count += 1
                        db.commit()
                        storage_path, content_type = generate_and_save_image(
                            card.image_prompt,
                            deck_id=deck_id,
                            card_id=card.id,
                        )
                        asset.storage_path = storage_path
                        asset.content_type = content_type
                        db.commit()
                        abs_path = os.path.join(getattr(settings, "image_storage_dir", "uploads"), storage_path)
                        concept_for_eval.image_prompt = card.image_prompt
                        concept_for_eval.description = card.description or ""
                        eval_result = run_evaluator(
                            style_bible=style_bible.content,
                            concept=concept_for_eval,
                            image_path=abs_path,
                        )
                        card.evaluation_feedback = eval_result.feedback
                        db.commit()
                        if eval_result.decision == "APPROVE":
                            card.status = "approved"
                            db.commit()
                            logger.info("Evaluator APPROVE for card %s (deck %s) after retry %s", card.id, deck_id, card.retry_count)
                            break
                    else:
                        card.status = "failed_retries"
                        db.commit()
                        logger.info("Card %s (deck %s) failed after %s retries", card.id, deck_id, card.retry_count)
            except Exception as img_err:
                logger.exception("Image generation failed for card %s: %s", card.id, img_err)
                card.status = "concept"
                db.commit()
                raise
        # All cards processed: build zip + PDF, then mark deck complete
        build_exports(deck_id, db)
        deck.status = "complete"
        job.status = "complete"
        db.commit()
    except Exception as e:
        logger.exception("Deck job %s failed: %s", job.id, e)
        job.status = "failed"
        db.commit()
        raise
