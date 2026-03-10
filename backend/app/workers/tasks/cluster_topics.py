import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.intelligence import ConversationAnalysis, TopicCluster
from app.models.organizational import Workspace
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(time_limit=600)
def cluster_topics() -> dict:
    return asyncio.run(_cluster())


async def _cluster() -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Workspace.id))
            workspace_ids = [row[0] for row in result.all()]

            total_clusters = 0
            for ws_id in workspace_ids:
                count = await _cluster_workspace(session, ws_id)
                total_clusters += count

            await session.commit()
            return {"status": "success", "total_clusters": total_clusters}
        except Exception:
            await session.rollback()
            raise


async def _cluster_workspace(session, workspace_id: uuid.UUID) -> int:
    now = datetime.now(timezone.utc)
    cutoff_28d = now - timedelta(days=28)

    result = await session.execute(
        select(ConversationAnalysis.summary, ConversationAnalysis.conversation_id).where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.summary.isnot(None),
            ConversationAnalysis.created_at >= cutoff_28d,
        )
    )
    rows = result.all()
    if len(rows) < 10:
        return 0

    summaries = [row[0] for row in rows]
    conversation_ids = [row[1] for row in rows]

    try:
        from bertopic import BERTopic
        from sklearn.feature_extraction.text import CountVectorizer

        vectorizer = CountVectorizer(stop_words="english")
        topic_model = BERTopic(
            min_topic_size=3,
            vectorizer_model=vectorizer,
            calculate_probabilities=False,
            verbose=False,
        )
        topics, _ = topic_model.fit_transform(summaries)
    except Exception as e:
        logger.error(f"Topic clustering failed for workspace {workspace_id}: {e}")
        return 0

    cutoff_7d = now - timedelta(days=7)
    topic_conversations: dict[int, list] = {}

    for i, topic_id in enumerate(topics):
        if topic_id == -1:
            continue
        topic_conversations.setdefault(topic_id, []).append(conversation_ids[i])

    result_7d = await session.execute(
        select(ConversationAnalysis.summary).where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.summary.isnot(None),
            ConversationAnalysis.created_at >= cutoff_7d,
        )
    )
    len(result_7d.all())
    count_28d = len(rows)
    count_28d / 4.0

    existing_labels = set()
    existing_result = await session.execute(select(TopicCluster.label).where(TopicCluster.workspace_id == workspace_id))
    for row in existing_result.all():
        existing_labels.add(row[0])

    created = 0
    for topic_id, conv_ids in topic_conversations.items():
        topic_info = topic_model.get_topic(topic_id)
        keywords = [word for word, _ in topic_info[:10]] if topic_info else []
        label = ", ".join(keywords[:5]) if keywords else f"Topic {topic_id}"

        topic_7d_count = sum(1 for i, t in enumerate(topics) if t == topic_id and i < len(rows))
        topic_28d_count = len(conv_ids)
        topic_baseline = topic_28d_count / 4.0

        anomaly_detected = False
        anomaly_type = None
        if topic_baseline > 0 and topic_7d_count > 2 * topic_baseline:
            anomaly_detected = True
            anomaly_type = "spike"
        if label not in existing_labels:
            anomaly_detected = True
            anomaly_type = "new_topic"

        volume_trend = {
            "7d": topic_7d_count,
            "28d": topic_28d_count,
            "baseline_weekly": round(topic_baseline, 1),
        }

        cluster = TopicCluster(
            workspace_id=workspace_id,
            label=label,
            keywords=keywords,
            conversation_count=topic_28d_count,
            volume_trend=volume_trend,
            anomaly_detected=anomaly_detected,
            anomaly_type=anomaly_type,
            date_range_start=(now - timedelta(days=28)).date(),
            date_range_end=now.date(),
        )
        session.add(cluster)
        created += 1

    return created
