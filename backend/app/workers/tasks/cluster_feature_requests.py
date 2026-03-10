from app.workers.celery_app import celery_app


@celery_app.task(time_limit=600)
def cluster_feature_requests() -> dict:
    # Feature request clustering removed in pulselite simplification
    return {"status": "disabled"}
