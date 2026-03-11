# backend/app/services/copilot/executor.py
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversations import Conversation, Message
from app.models.knowledge import Chatbot, KnowledgeBase, Document
from app.models.actions import ChatbotAction


async def execute_tool(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    tool_name: str,
    args: dict,
) -> object:
    """Execute a server-side copilot tool and return a JSON-serialisable result."""
    try:
        if tool_name == "fetch_chatbots":
            return await _fetch_chatbots(db, workspace_id)
        elif tool_name == "fetch_chatbot":
            return await _fetch_chatbot(db, workspace_id, args["chatbot_id"])
        elif tool_name == "fetch_conversations":
            return await _fetch_conversations(db, workspace_id, args.get("filters") or {})
        elif tool_name == "fetch_conversation":
            return await _fetch_conversation(db, workspace_id, args["conversation_id"])
        elif tool_name == "fetch_metrics":
            return await _fetch_metrics(db, workspace_id, args.get("period", "30d"))
        elif tool_name == "fetch_credits":
            return await _fetch_credits(db, workspace_id)
        elif tool_name == "fetch_documents":
            return await _fetch_documents(db, workspace_id, args["chatbot_id"])
        elif tool_name == "fetch_actions":
            return await _fetch_actions(db, workspace_id, args["chatbot_id"])
        elif tool_name == "update_chatbot":
            return await _update_chatbot(db, workspace_id, args["chatbot_id"], args["fields"])
        elif tool_name == "create_chatbot":
            return await _create_chatbot(db, workspace_id, args["name"], args.get("url"))
        elif tool_name == "delete_chatbot":
            return await _delete_chatbot(db, workspace_id, args["chatbot_id"])
        elif tool_name == "run_crawl":
            return await _run_crawl(db, workspace_id, args["chatbot_id"], args["url"])
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        return {"error": str(exc)}


async def _fetch_chatbots(db: AsyncSession, workspace_id: uuid.UUID) -> list:
    result = await db.execute(
        select(Chatbot).where(Chatbot.workspace_id == workspace_id)
    )
    bots = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "name": b.name,
            "display_name": b.display_name,
            "is_active": b.is_active,
            "llm_model": b.llm_model,
            "tone": b.tone,
            "confidence_threshold": b.confidence_threshold,
        }
        for b in bots
    ]


async def _fetch_chatbot(db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: str) -> dict:
    result = await db.execute(
        select(Chatbot).where(
            Chatbot.id == uuid.UUID(chatbot_id),
            Chatbot.workspace_id == workspace_id,
        )
    )
    b = result.scalar_one_or_none()
    if not b:
        return {"error": "Chatbot not found"}
    return {
        "id": str(b.id),
        "name": b.name,
        "display_name": b.display_name,
        "is_active": b.is_active,
        "llm_model": b.llm_model,
        "llm_provider": b.llm_provider,
        "tone": b.tone,
        "system_prompt": b.system_prompt,
        "welcome_message": b.welcome_message,
        "fallback_message": b.fallback_message,
        "confidence_threshold": b.confidence_threshold,
        "temperature": b.temperature,
        "use_reranking": b.use_reranking,
        "use_hybrid_retrieval": b.use_hybrid_retrieval,
    }


async def _fetch_conversations(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    filters: dict,
) -> list:
    # Conversations belong to workspace directly (workspace_id column exists)
    stmt = (
        select(Conversation)
        .where(Conversation.workspace_id == workspace_id)
        .order_by(Conversation.created_at.desc())
    )
    if filters.get("escalated"):
        # Escalated conversations have status="escalated" or escalation_reason set
        stmt = stmt.where(Conversation.status == "escalated")
    if filters.get("chatbot_id"):
        stmt = stmt.where(Conversation.chatbot_id == uuid.UUID(filters["chatbot_id"]))
    limit = min(int(filters.get("limit", 20)), 50)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    convs = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "chatbot_id": str(c.chatbot_id) if c.chatbot_id else None,
            "status": c.status,
            "escalation_reason": c.escalation_reason,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in convs
    ]


async def _fetch_conversation(
    db: AsyncSession, workspace_id: uuid.UUID, conversation_id: str
) -> dict:
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == uuid.UUID(conversation_id),
            Conversation.workspace_id == workspace_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return {"error": "Conversation not found"}

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    msgs = msg_result.scalars().all()
    return {
        "id": str(conv.id),
        "chatbot_id": str(conv.chatbot_id) if conv.chatbot_id else None,
        "status": conv.status,
        "escalation_reason": conv.escalation_reason,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "messages": [
            {
                "author_type": m.author_type,   # "user" | "bot" | "agent"
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }


async def _fetch_metrics(db: AsyncSession, workspace_id: uuid.UUID, period: str) -> dict:
    days = 7 if period == "7d" else 30
    since = datetime.now(timezone.utc) - timedelta(days=days)

    from sqlalchemy import func

    total_result = await db.execute(
        select(func.count(Conversation.id))
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= since,
        )
    )
    total = total_result.scalar() or 0

    escalated_result = await db.execute(
        select(func.count(Conversation.id))
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= since,
            Conversation.escalation_reason.isnot(None),
        )
    )
    escalated = escalated_result.scalar() or 0

    return {
        "period": period,
        "total_conversations": total,
        "escalated_conversations": escalated,
        "escalation_rate": round(escalated / total, 3) if total else 0,
    }


async def _fetch_credits(db: AsyncSession, workspace_id: uuid.UUID) -> dict:
    from app.services.credits import get_balance
    from app.models.organizational import Workspace

    balance = await get_balance(db, workspace_id)
    ws_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = ws_result.scalar_one_or_none()
    return {
        "balance": balance,
        "plan": ws.plan if ws else "unknown",
    }


async def _fetch_documents(db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: str) -> list:
    kb_result = await db.execute(
        select(KnowledgeBase)
        .where(
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.chatbot_id == uuid.UUID(chatbot_id),
        )
    )
    kb = kb_result.scalar_one_or_none()
    if not kb:
        return []

    doc_result = await db.execute(
        select(Document).where(Document.knowledge_base_id == kb.id).limit(50)
    )
    docs = doc_result.scalars().all()
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "source_type": d.source_type,
            "status": d.status,
        }
        for d in docs
    ]


async def _fetch_actions(db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: str) -> list:
    result = await db.execute(
        select(ChatbotAction)
        .join(Chatbot, ChatbotAction.chatbot_id == Chatbot.id)
        .where(
            Chatbot.workspace_id == workspace_id,
            ChatbotAction.chatbot_id == uuid.UUID(chatbot_id),
        )
    )
    actions = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "action_type": a.action_type,
            "is_enabled": a.is_enabled,
            "trigger_description": a.trigger_description,
        }
        for a in actions
    ]


async def _update_chatbot(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: str,
    fields: dict,
) -> dict:
    result = await db.execute(
        select(Chatbot).where(
            Chatbot.id == uuid.UUID(chatbot_id),
            Chatbot.workspace_id == workspace_id,
        )
    )
    bot = result.scalar_one_or_none()
    if not bot:
        return {"error": "Chatbot not found"}

    allowed = {
        "name", "display_name", "system_prompt", "tone", "welcome_message",
        "fallback_message", "confidence_threshold", "temperature", "llm_model",
        "is_active", "use_reranking", "use_hybrid_retrieval",
    }
    for key, value in fields.items():
        if key in allowed:
            setattr(bot, key, value)

    await db.commit()
    return {"ok": True, "chatbot_id": chatbot_id, "updated": [k for k in fields.keys() if k in allowed]}


async def _create_chatbot(
    db: AsyncSession, workspace_id: uuid.UUID, name: str, url: str | None
) -> dict:
    from app.services.chatbot_service import create_chatbot as svc_create
    bot = await svc_create(db, workspace_id, name=name)
    await db.commit()
    result: dict = {"ok": True, "chatbot_id": str(bot.id), "name": bot.name}
    if url:
        from app.services.crawl_service import prepare_crawl
        from app.workers.tasks.crawl_website import crawl_website
        job_id, _kb_id = await prepare_crawl(
            db, workspace_id, url, max_pages=50, chatbot_id=bot.id
        )
        crawl_website.delay(job_id)
        result["crawl_job_id"] = job_id
    return result


async def _delete_chatbot(
    db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: str
) -> dict:
    result = await db.execute(
        select(Chatbot).where(
            Chatbot.id == uuid.UUID(chatbot_id),
            Chatbot.workspace_id == workspace_id,
        )
    )
    bot = result.scalar_one_or_none()
    if not bot:
        return {"error": "Chatbot not found"}
    await db.delete(bot)
    await db.commit()
    return {"ok": True, "deleted": chatbot_id}


async def _run_crawl(
    db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: str, url: str
) -> dict:
    from app.services.crawl_service import prepare_crawl
    from app.workers.tasks.crawl_website import crawl_website

    # Verify chatbot belongs to this workspace
    result = await db.execute(
        select(Chatbot).where(
            Chatbot.id == uuid.UUID(chatbot_id),
            Chatbot.workspace_id == workspace_id,
        )
    )
    bot = result.scalar_one_or_none()
    if not bot:
        return {"error": "Chatbot not found"}

    # prepare_crawl signature: (db, workspace_id, url, max_pages, kb_id=None, chatbot_id=None)
    job_id, _kb_id = await prepare_crawl(
        db, workspace_id, url, max_pages=50, chatbot_id=uuid.UUID(chatbot_id)
    )
    crawl_website.delay(job_id)
    return {"ok": True, "crawl_job_id": job_id}
