from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "pulse",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "sync-stale-documents": {
            "task": "app.workers.tasks.sync_documents.sync_stale_documents",
            "schedule": 3600.0,  # every hour
        },
        "cluster-gaps": {
            "task": "app.workers.tasks.cluster_gaps.cluster_gaps",
            "schedule": crontab(hour=3, minute=0),
        },
        "weekly-digest": {
            "task": "app.workers.tasks.weekly_digest.send_weekly_digest_task",
            "schedule": crontab(hour=9, minute=0, day_of_week=1),
        },
        "purge-old-data": {
            "task": "app.workers.tasks.purge_old_data.purge_old_data",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)

celery_app.conf.include = [
    "app.workers.tasks.ingest_document",
    "app.workers.tasks.analyze_conversation",
    "app.workers.tasks.auto_recharge",
    "app.workers.tasks.cluster_gaps",
    "app.workers.tasks.compute_sentiment_trends",
    "app.workers.tasks.gdpr_export",
    "app.workers.tasks.purge_old_data",
    "app.workers.tasks.reindex_article",
    "app.workers.tasks.sync_documents",
    "app.workers.tasks.weekly_digest",
    "app.workers.tasks.crawl_website",
]
