import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models.intelligence import GapCluster, GapEvent
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(time_limit=600)
def cluster_gaps() -> dict:
    return asyncio.run(_cluster())


async def _cluster() -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                select(GapEvent.workspace_id, func.count())
                .where(GapEvent.gap_cluster_id.is_(None))
                .group_by(GapEvent.workspace_id)
            )
            workspace_counts = result.all()

            total_clustered = 0
            for ws_id, count in workspace_counts:
                if count < 10:
                    logger.info(f"Workspace {ws_id}: only {count} unclustered events, skipping (need >= 10)")
                    continue

                clustered = await _cluster_workspace(session, ws_id)
                total_clustered += clustered

            await session.commit()
            return {"status": "success", "total_clustered": total_clustered}
        except Exception:
            await session.rollback()
            raise


async def _cluster_workspace(session, workspace_id: uuid.UUID) -> int:
    result = await session.execute(
        select(GapEvent).where(GapEvent.workspace_id == workspace_id, GapEvent.gap_cluster_id.is_(None))
    )
    events = list(result.scalars().all())

    queries = [e.query for e in events]

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
        topics, _ = topic_model.fit_transform(queries)

    except Exception as e:
        logger.error(f"BERTopic clustering failed for workspace {workspace_id}: {e}")
        return 0

    topic_events: dict[int, list[GapEvent]] = {}
    for event, topic_id in zip(events, topics):
        if topic_id == -1:
            continue
        topic_events.setdefault(topic_id, []).append(event)

    clustered_count = 0
    for topic_id, group_events in topic_events.items():
        topic_info = topic_model.get_topic(topic_id)
        keywords = [word for word, _ in topic_info[:10]] if topic_info else []
        topic_label = ", ".join(keywords[:5]) if keywords else f"Topic {topic_id}"
        representative_query = group_events[0].query

        cluster = GapCluster(
            workspace_id=workspace_id,
            topic_label=topic_label,
            topic_keywords=keywords,
            gap_count=len(group_events),
            representative_query=representative_query,
            status="open",
            clustered_at=datetime.now(timezone.utc),
        )
        session.add(cluster)
        await session.flush()

        for event in group_events:
            event.gap_cluster_id = cluster.id
            clustered_count += 1

    if topic_events:
        from app.workers.tasks.auto_draft_article import auto_draft_articles

        auto_draft_articles.delay(str(workspace_id))

    return clustered_count
