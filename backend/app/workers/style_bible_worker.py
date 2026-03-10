"""Process style-bible jobs: run crew, write result to style_bibles."""

import json
import logging

from sqlalchemy.orm import Session

from app.crews.style_bible_crew import run_style_bible_crew
from app.models import Job, StyleBible
from app.workers.queue import STYLE_BIBLE_JOB_TYPE

logger = logging.getLogger(__name__)


def get_next_style_bible_job(db: Session) -> Job | None:
    """Return one pending style_bible job or None."""
    return (
        db.query(Job)
        .filter(Job.type == STYLE_BIBLE_JOB_TYPE, Job.status == "pending")
        .order_by(Job.created_at)
        .first()
    )


def process_style_bible_job(db: Session, job: Job) -> None:
    """
    Run the style-bible crew for this job and update style_bibles row and job status.
    On success: style_bible.content = markdown, status = ready; job.status = complete.
    On failure: style_bible.status = draft (so user can retry); job.status = failed.
    """
    payload = json.loads(job.payload or "{}")
    style_bible_id = payload.get("style_bible_id")
    if not style_bible_id:
        job.status = "failed"
        db.commit()
        raise ValueError("Job payload missing style_bible_id")

    style_bible = db.query(StyleBible).filter(StyleBible.id == style_bible_id).first()
    if not style_bible:
        job.status = "failed"
        db.commit()
        raise ValueError(f"StyleBible {style_bible_id} not found")

    creative_direction = payload.get("creative_direction", "")
    medium = payload.get("medium", "")
    deck_size = int(payload.get("deck_size", 78))
    feedback = payload.get("feedback")

    try:
        result = run_style_bible_crew(
            creative_direction=creative_direction,
            medium=medium,
            deck_size=deck_size,
            feedback=feedback,
        )
        content = result.to_markdown()
        style_bible.content = content
        style_bible.status = "ready"
        job.status = "complete"
        db.commit()
        logger.info("Style bible job %s completed for style_bible %s", job.id, style_bible_id)
    except Exception as e:
        logger.exception("Style bible job %s failed: %s", job.id, e)
        style_bible.status = "draft"
        job.status = "failed"
        db.commit()
        raise
