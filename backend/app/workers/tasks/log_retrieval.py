import asyncio
import uuid


from app.database import async_session_factory
from app.models.intelligence import GapEvent, RetrievalLog
from app.workers.celery_app import celery_app


@celery_app.task
def log_retrieval_task(
    workspace_id: str,
    chatbot_id: str,
    conversation_id: str,
    message_id: str,
    query: str,
    confidence_score: float,
    confidence_avg: float,
    retrieved_chunk_ids: list[str],
    escalated: bool,
) -> dict:
    return asyncio.run(
        _log(
            uuid.UUID(workspace_id),
            uuid.UUID(chatbot_id),
            uuid.UUID(conversation_id),
            uuid.UUID(message_id),
            query,
            confidence_score,
            confidence_avg,
            [uuid.UUID(cid) for cid in retrieved_chunk_ids],
            escalated,
        )
    )


async def _log(
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    query: str,
    confidence_score: float,
    confidence_avg: float,
    retrieved_chunk_ids: list[uuid.UUID],
    escalated: bool,
) -> dict:
    async with async_session_factory() as session:
        try:
            log = RetrievalLog(
                workspace_id=workspace_id,
                chatbot_id=chatbot_id,
                conversation_id=conversation_id,
                message_id=message_id,
                query=query,
                confidence_score=confidence_score,
                confidence_avg=confidence_avg,
                retrieved_chunk_ids=retrieved_chunk_ids,
                escalated=escalated,
            )
            session.add(log)
            await session.flush()

            if escalated:
                gap_event = GapEvent(
                    workspace_id=workspace_id,
                    retrieval_log_id=log.id,
                    query=query,
                    confidence_score=confidence_score,
                )
                session.add(gap_event)

            await session.commit()
            return {"status": "logged", "retrieval_log_id": str(log.id)}
        except Exception:
            await session.rollback()
            raise
