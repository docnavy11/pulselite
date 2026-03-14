import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import async_session_factory, engine
from app.models.intelligence import GapCluster, GapEvent, RetrievalLog
from app.services.realtime import emit_task_event
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, time_limit=600)
def cluster_gaps(self) -> dict:
    return asyncio.run(_cluster(self.request.id))


async def _cluster(task_id: str) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            from app.models.organizational import Workspace

            # Load workspace intelligence configs to check which have clustering enabled
            ws_result = await session.execute(select(Workspace.id, Workspace.intelligence_config))
            disabled_ws = {
                row[0] for row in ws_result.all()
                if not (row[1] or {}).get("gap_clustering", True)
            }

            result = await session.execute(
                select(GapEvent.workspace_id, func.count())
                .where(GapEvent.gap_cluster_id.is_(None))
                .group_by(GapEvent.workspace_id)
            )
            workspace_counts = result.all()

            total_clustered = 0
            for ws_id, count in workspace_counts:
                if ws_id in disabled_ws:
                    logger.info(f"Workspace {ws_id}: gap clustering disabled, skipping")
                    continue
                if count < 10:
                    logger.info(f"Workspace {ws_id}: only {count} unclustered events, skipping (need >= 10)")
                    continue

                await emit_task_event(str(ws_id), "started", "cluster_gaps", task_id,
                                      detail=f"{count} unclustered events")
                clustered = await _cluster_workspace(session, ws_id)
                total_clustered += clustered
                await emit_task_event(str(ws_id), "completed", "cluster_gaps", task_id,
                                      detail=f"Clustered {clustered} events")

            await session.commit()
            return {"status": "success", "total_clustered": total_clustered}
        except Exception:
            await session.rollback()
            raise


async def _cluster_workspace(session, workspace_id: uuid.UUID) -> int:
    result = await session.execute(
        select(GapEvent, RetrievalLog.chatbot_id)
        .join(RetrievalLog, GapEvent.retrieval_log_id == RetrievalLog.id)
        .where(GapEvent.workspace_id == workspace_id, GapEvent.gap_cluster_id.is_(None))
    )
    rows = result.all()
    events = [row[0] for row in rows]
    event_chatbot_map = {row[0].id: row[1] for row in rows}

    queries = [e.query for e in events]

    try:
        from bertopic import BERTopic  # type: ignore[import-untyped]
        from sklearn.feature_extraction.text import CountVectorizer  # type: ignore[import-untyped]

        vectorizer = CountVectorizer(stop_words="english")
        topic_model = BERTopic(
            min_topic_size=3,
            vectorizer_model=vectorizer,
            calculate_probabilities=False,
            verbose=False,
        )
        topics, _ = topic_model.fit_transform(queries)

    except ImportError:
        logger.error(
            "BERTopic or sklearn not installed — gap clustering disabled. "
            "Install with: pip install bertopic scikit-learn"
        )
        return 0
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

        # Determine most common chatbot for this cluster
        chatbot_ids = [event_chatbot_map.get(e.id) for e in group_events if event_chatbot_map.get(e.id)]
        most_common_chatbot = max(set(chatbot_ids), key=chatbot_ids.count) if chatbot_ids else None

        cluster = GapCluster(
            workspace_id=workspace_id,
            chatbot_id=most_common_chatbot,
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

    return clustered_count
