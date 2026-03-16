import asyncio
import logging
import uuid
from datetime import datetime, timezone

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import func, select

from app.database import async_session_factory, engine
from app.models.intelligence import GapCluster, GapEvent, RetrievalLog
from app.services.llm import get_internal_model, get_llm_client
from app.services.realtime import emit_task_event
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=540, time_limit=600)
def cluster_gaps(self) -> dict:
    try:
        return asyncio.run(_cluster(self.request.id))
    except MaxRetriesExceededError:
        logger.error("cluster_gaps failed after max retries")
        return {"status": "failed", "reason": "max retries exceeded"}
    except Exception as exc:
        raise self.retry(exc=exc)


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
                if count < 3:
                    logger.info(f"Workspace {ws_id}: only {count} unclustered events, skipping (need >= 3)")
                    continue

                ws_task_id = f"{task_id}:{ws_id}"
                await emit_task_event(str(ws_id), "started", "cluster_gaps", ws_task_id,
                                      detail=f"{count} unclustered events")
                clustered = await _cluster_workspace(session, ws_id)
                total_clustered += clustered
                await emit_task_event(str(ws_id), "completed", "cluster_gaps", ws_task_id,
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

    # For small sets, BERTopic's dimensionality reduction fails — group all into one cluster
    if len(queries) < 6:
        topic_events: dict[int, list[GapEvent]] = {0: events}
    else:
        try:
            from bertopic import BERTopic  # type: ignore[import-untyped]
            from sklearn.feature_extraction.text import CountVectorizer  # type: ignore[import-untyped]

            vectorizer = CountVectorizer(stop_words="english")
            topic_model = BERTopic(
                min_topic_size=2,
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

        topic_events = {}
        for event, topic_id in zip(events, topics):
            if topic_id == -1:
                continue
            topic_events.setdefault(topic_id, []).append(event)

    # Generate human-readable labels for all clusters in a single LLM call
    topic_queries: dict[int, list[str]] = {}
    for topic_id, group_events in topic_events.items():
        topic_queries[topic_id] = [e.query for e in group_events]

    labels = await _generate_topic_labels(session, workspace_id, topic_queries)

    # Extract keywords from BERTopic model if available, otherwise leave empty
    topic_keywords_map: dict[int, list[str]] = {}
    if len(queries) >= 6:
        for tid in topic_events:
            topic_info = topic_model.get_topic(tid)  # type: ignore[possibly-undefined]
            topic_keywords_map[tid] = [word for word, _ in topic_info[:10]] if topic_info else []

    clustered_count = 0
    for topic_id, group_events in topic_events.items():
        keywords = topic_keywords_map.get(topic_id, [])
        topic_label = labels.get(topic_id, ", ".join(keywords[:5]) if keywords else f"Topic {topic_id}")

        # Pick the most descriptive query as representative (longest meaningful one)
        representative_query = max(
            (e.query for e in group_events if len(e.query.strip()) > 5),
            key=len,
            default=group_events[0].query,
        )

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


async def _generate_topic_labels(
    session, workspace_id: uuid.UUID, topic_queries: dict[int, list[str]]
) -> dict[int, str]:
    """Use LLM to generate short, human-readable labels for each cluster."""
    if not topic_queries:
        return {}

    model = await get_internal_model(session, workspace_id)
    client = get_llm_client("openrouter")

    # Build a prompt listing all clusters with their queries
    cluster_lines = []
    for topic_id, queries in topic_queries.items():
        quoted = ", ".join(f'"{q}"' for q in queries[:8])
        cluster_lines.append(f"Cluster {topic_id}: {quoted}")

    prompt = (
        "Below are clusters of unanswered user questions grouped by topic.\n"
        "For each cluster, write a short label (2-6 words) that describes what users are asking about.\n"
        "The label should be human-readable and describe the topic, not repeat the questions.\n\n"
        + "\n".join(cluster_lines)
        + "\n\nRespond with one line per cluster in this exact format:\n"
        "Cluster <id>: <label>\n"
        "Nothing else."
    )

    try:
        messages = [
            {"role": "system", "content": "You generate short topic labels for groups of similar questions. Be concise and descriptive."},
            {"role": "user", "content": prompt},
        ]
        response = await client.generate(
            messages=messages,
            model=model,
            max_tokens=300,
            temperature=0.3,
        )

        labels: dict[int, str] = {}
        for line in response.strip().splitlines():
            line = line.strip()
            if line.startswith("Cluster "):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    try:
                        tid = int(parts[0].replace("Cluster", "").strip())
                        labels[tid] = parts[1].strip()
                    except ValueError:
                        continue
        return labels
    except Exception as e:
        logger.warning(f"LLM label generation failed, falling back to keywords: {e}")
        return {}
