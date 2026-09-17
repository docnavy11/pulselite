"""Scheduled jobs — replaces Celery Beat.

Uses APScheduler's AsyncIOScheduler for cron-style recurring tasks.
Each job is a thin wrapper that submits work to the Postgres job queue.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.background.runner import submit_job

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _submit_cluster_gaps():
    await submit_job("cluster_gaps")


async def _submit_sentiment_trends():
    await submit_job("compute_sentiment_trends")


async def _submit_close_stale():
    await submit_job("close_stale_conversations")


async def _submit_sync_documents():
    await submit_job("sync_documents")


async def _submit_purge_data():
    await submit_job("purge_old_data")


def setup_scheduler():
    scheduler.add_job(_submit_cluster_gaps, "cron", hour=3, id="cluster_gaps")
    scheduler.add_job(_submit_sentiment_trends, "cron", hour=4, id="sentiment_trends")
    scheduler.add_job(_submit_close_stale, "cron", hour="*/6", id="close_stale")
    scheduler.add_job(_submit_sync_documents, "cron", hour=2, id="sync_documents")
    scheduler.add_job(_submit_purge_data, "cron", hour=5, day_of_week="sun", id="purge_data")
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
