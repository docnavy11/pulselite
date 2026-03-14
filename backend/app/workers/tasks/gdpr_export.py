import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory, engine
from app.models.contacts import Contact
from app.models.conversations import Conversation
from app.models.organizational import Workspace
from app.services.realtime import emit_task_event
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

EXPORT_DIR = "/app/data/exports"


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def export_workspace_data(self, workspace_id: str, export_id: str) -> dict:
    try:
        return asyncio.run(_export(uuid.UUID(workspace_id), export_id, self.request.id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _export(workspace_id: uuid.UUID, export_id: str, task_id: str) -> dict:
    await engine.dispose()
    os.makedirs(EXPORT_DIR, mode=0o700, exist_ok=True)
    export_path = os.path.join(EXPORT_DIR, f"{export_id}.json")

    async with async_session_factory() as session:
        try:
            ws_result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = ws_result.scalar_one_or_none()
            if not workspace:
                return {"status": "error", "detail": "Workspace not found"}

            await emit_task_event(workspace_id, "started", "export_data", task_id)

            contacts_result = await session.execute(
                select(Contact).where(Contact.workspace_id == workspace_id).options(selectinload(Contact.events))
            )
            contacts = contacts_result.scalars().all()

            conv_result = await session.execute(
                select(Conversation)
                .where(Conversation.workspace_id == workspace_id)
                .options(selectinload(Conversation.messages))
            )
            conversations = conv_result.scalars().all()

            export_data = {
                "workspace": {
                    "id": str(workspace.id),
                    "name": workspace.name,
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                },
                "contacts": [
                    {
                        "id": str(c.id),
                        "email": c.email,
                        "name": c.name,
                        "lead_score": c.lead_score,
                        "events": [
                            {"event_name": e.event_name, "created_at": e.created_at.isoformat()} for e in c.events
                        ],
                    }
                    for c in contacts
                ],
                "conversations": [
                    {
                        "id": str(conv.id),
                        "status": conv.status,
                        "created_at": conv.created_at.isoformat(),
                        "messages": [
                            {
                                "content": m.content,
                                "author_type": m.author_type,
                                "created_at": m.created_at.isoformat(),
                            }
                            for m in conv.messages
                        ],
                    }
                    for conv in conversations
                ],
            }

            with open(export_path, "w") as f:
                json.dump(export_data, f, indent=2)

            await emit_task_event(workspace_id, "completed", "export_data", task_id, detail=f"Exported {len(contacts)} contacts, {len(conversations)} conversations")
            return {"status": "success", "export_id": export_id, "path": export_path}
        except Exception as exc:
            await session.rollback()
            await emit_task_event(workspace_id, "completed", "export_data", task_id, error=str(exc))
            raise
