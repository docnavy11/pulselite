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
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.crawl_website.*": {"queue": "crawl"},
        "app.workers.tasks.ingest_document.*": {"queue": "crawl"},
        "app.workers.tasks.deliver_webhook.*": {"queue": "webhooks"},
        "app.workers.tasks.cluster_gaps.*": {"queue": "analytics"},
        "app.workers.tasks.compute_sentiment_trends.*": {"queue": "analytics"},
        "app.workers.tasks.purge_old_data.*": {"queue": "analytics"},
    },
    # Each prefork worker uses ~250MB RAM. Tasks are I/O-bound (LLM API calls, DB queries),
    # so 2 workers is enough for most self-hosted deployments. Increase if you have many
    # concurrent crawl/ingestion jobs. Set via CELERY_WORKER_CONCURRENCY in .env.
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    beat_schedule={
        "sync-stale-documents": {
            "task": "app.workers.tasks.sync_documents.sync_stale_documents",
            "schedule": 3600.0,  # every hour
        },
        "cluster-gaps": {
            "task": "app.workers.tasks.cluster_gaps.cluster_gaps",
            "schedule": crontab(hour=3, minute=0),
        },
        "compute-sentiment-trends": {
            "task": "app.workers.tasks.compute_sentiment_trends.compute_sentiment_trends",
            "schedule": crontab(hour=4, minute=0),  # daily at 04:00 UTC, after cluster-gaps at 03:00
        },
        "send-report": {
            "task": "app.workers.tasks.send_report.send_report_task",
            "schedule": 3600.0,  # every hour — checks per-workspace timestamps
        },
        "purge-old-data": {
            "task": "app.workers.tasks.purge_old_data.purge_old_data",
            "schedule": crontab(hour=3, minute=0),
        },
        "close-stale-conversations": {
            "task": "app.workers.tasks.close_stale_conversations.close_stale_conversations",
            "schedule": 300.0,  # every 5 minutes
        },
    },
)

celery_app.conf.include = [
    "app.workers.tasks.ingest_document",
    "app.workers.tasks.run_autoconfig",
    "app.workers.tasks.analyze_conversation",
    "app.workers.tasks.auto_recharge",
    "app.workers.tasks.cluster_gaps",
    "app.workers.tasks.close_stale_conversations",
    "app.workers.tasks.compute_sentiment_trends",
    "app.workers.tasks.gdpr_export",
    "app.workers.tasks.purge_old_data",
    "app.workers.tasks.reindex_article",
    "app.workers.tasks.sync_documents",
    "app.workers.tasks.send_report",
    "app.workers.tasks.crawl_website",
    "app.workers.tasks.generate_qa",
    "app.workers.tasks.deliver_webhook",
]
