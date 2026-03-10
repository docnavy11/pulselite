import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.intelligence import IntelligenceSignal, TopicCluster
from app.models.organizational import Workspace
from app.services.integrations.linear import create_linear_issue
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(time_limit=600)
def cluster_feature_requests() -> dict:
    return asyncio.run(_cluster())


async def _cluster() -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Workspace.id))
            workspace_ids = [row[0] for row in result.all()]

            total = 0
            for ws_id in workspace_ids:
                count = await _cluster_workspace(session, ws_id)
                total += count

            await session.commit()
            return {"status": "success", "total_clusters": total}
        except Exception:
            await session.rollback()
            raise


async def _cluster_workspace(session, workspace_id: uuid.UUID) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=28)

    result = await session.execute(
        select(IntelligenceSignal).where(
            IntelligenceSignal.workspace_id == workspace_id,
            IntelligenceSignal.signal_type == "feature_request",
            IntelligenceSignal.created_at >= cutoff,
        )
    )
    signals = list(result.scalars().all())
    if len(signals) < 5:
        return 0

    texts = []
    for s in signals:
        payload = s.payload or {}
        text = payload.get("description", "") or payload.get("text", "") or str(payload)
        texts.append(text)

    try:
        from bertopic import BERTopic
        from sklearn.feature_extraction.text import CountVectorizer

        vectorizer = CountVectorizer(stop_words="english")
        topic_model = BERTopic(
            min_topic_size=2,
            vectorizer_model=vectorizer,
            calculate_probabilities=False,
            verbose=False,
        )
        topics, _ = topic_model.fit_transform(texts)
    except Exception as e:
        logger.error(f"Feature request clustering failed for workspace {workspace_id}: {e}")
        return 0

    topic_groups: dict[int, list] = {}
    for i, topic_id in enumerate(topics):
        if topic_id == -1:
            continue
        topic_groups.setdefault(topic_id, []).append(signals[i])

    created = 0
    for topic_id, group_signals in topic_groups.items():
        topic_info = topic_model.get_topic(topic_id)
        keywords = [word for word, _ in topic_info[:10]] if topic_info else []
        label = "FR: " + (", ".join(keywords[:5]) if keywords else f"Feature {topic_id}")

        cluster = TopicCluster(
            workspace_id=workspace_id,
            label=label,
            keywords=keywords,
            conversation_count=len(group_signals),
            volume_trend={"type": "feature_request", "count": len(group_signals)},
            date_range_start=(now - timedelta(days=28)).date(),
            date_range_end=now.date(),
        )
        session.add(cluster)

        first_signal = group_signals[0]
        representative = (
            (first_signal.payload or {}).get("description", "") or (first_signal.payload or {}).get("text", "") or ""
        )
        await create_linear_issue(
            session,
            workspace_id,
            title=f"Feature Request: {label}",
            description=f"Requested by {len(group_signals)} customers.\n\nRepresentative: {representative}",
        )

        created += 1

    return created
