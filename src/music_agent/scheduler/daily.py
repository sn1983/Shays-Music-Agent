"""Long-running mode: fire the pipeline every day at the configured local time."""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from music_agent.config import Settings
from music_agent.pipeline import DailySongPipeline, summarise

logger = logging.getLogger(__name__)


def run_scheduler(settings: Settings, pipeline: DailySongPipeline | None = None) -> None:
    """Block forever, publishing once a day at POST_TIME in TIMEZONE."""
    pipeline = pipeline or DailySongPipeline(settings)
    scheduler = BlockingScheduler(timezone=settings.timezone)

    def job() -> None:
        try:
            for result in pipeline.run(once_per_day=True):
                logger.info(summarise(result))
        except Exception:  # keep the scheduler alive across a bad day
            logger.exception("Daily run failed; will try again tomorrow.")

    scheduler.add_job(
        job,
        CronTrigger(
            hour=settings.post_hour,
            minute=settings.post_minute,
            timezone=settings.timezone,
        ),
        id="daily-song",
        name="Publish the daily song",
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )

    logger.info(
        "Scheduler started — next post at %s %s. Press Ctrl+C to stop.",
        settings.post_time,
        settings.timezone,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
