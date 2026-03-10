from app.workers.celery_app import celery_app


@celery_app.task(time_limit=600)
def cluster_topics() -> dict:
    # Topic clustering removed in pulselite simplification
    return {"status": "disabled"}
