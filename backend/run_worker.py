#!/usr/bin/env python3
"""
Poll the job queue and process style-bible and deck jobs.
Run in a separate terminal from the API server.

  cd backend && PYTHONPATH=. python run_worker.py
"""

import logging
import time

from app.db import SessionLocal, init_db
from app.workers.deck_worker import get_next_deck_job, process_deck_job
from app.workers.queue import DECK_JOB_TYPE, STYLE_BIBLE_JOB_TYPE
from app.workers.style_bible_worker import get_next_style_bible_job, process_style_bible_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLL_SECONDS = 2


def main():
    init_db()
    logger.info("Worker started; polling every %s s", POLL_SECONDS)
    while True:
        db = SessionLocal()
        try:
            job = get_next_style_bible_job(db) or get_next_deck_job(db)
            if job:
                try:
                    if job.type == STYLE_BIBLE_JOB_TYPE:
                        process_style_bible_job(db, job)
                    elif job.type == DECK_JOB_TYPE:
                        process_deck_job(db, job)
                    else:
                        logger.warning("Unknown job type: %s", job.type)
                except Exception as e:
                    logger.exception("Job %s failed: %s", job.id, e)
            else:
                time.sleep(POLL_SECONDS)
        finally:
            db.close()


if __name__ == "__main__":
    main()
