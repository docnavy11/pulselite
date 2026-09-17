"""Conversation routes — two-panel layout with filters."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversations import Conversation
from app.models.intelligence import ConversationAnalysis
from app.models.knowledge import Chatbot
from app.services.conversation_service import get_conversation, get_messages, list_conversations

router = APIRouter()


@router.get("/conversations", response_class=HTMLResponse)
async def conversation_list(
    request: Request,
    status: str | None = Query(None),
    chatbot_id: uuid.UUID | None = Query(None),
    outcome: str | None = Query(None),
    days: int | None = Query(None),
    selected: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace

    date_from = None
    if days:
        date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    conversations = await list_conversations(
        db,
        workspace.id,
        status_filter=status,
        chatbot_id=chatbot_id,
        outcome_filter=outcome,
        date_from=date_from,
    )

    # Load chatbots for filter dropdown
    chatbots = (
        (await db.execute(select(Chatbot).where(Chatbot.workspace_id == workspace.id, Chatbot.archived_at.is_(None))))
        .scalars()
        .all()
    )

    # Load selected conversation detail
    selected_conv = None
    selected_messages = []
    selected_analysis = None
    if selected:
        try:
            selected_conv = await get_conversation(db, selected, workspace.id)
            selected_messages = await get_messages(db, selected, workspace.id)
            analysis_result = await db.execute(
                select(ConversationAnalysis).where(ConversationAnalysis.conversation_id == selected)
            )
            selected_analysis = analysis_result.scalar_one_or_none()
        except Exception:
            pass

    return request.app.state.templates.TemplateResponse(
        "conversations/list.html",
        {
            "request": request,
            "conversations": conversations,
            "chatbots": chatbots,
            "status_filter": status,
            "chatbot_filter": chatbot_id,
            "days_filter": days,
            "selected": selected_conv,
            "messages": selected_messages,
            "analysis": selected_analysis,
        },
    )


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
async def conversation_detail(
    request: Request,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    conversation = await get_conversation(db, conversation_id, workspace.id)
    messages = await get_messages(db, conversation_id, workspace.id)
    analysis_result = await db.execute(
        select(ConversationAnalysis).where(ConversationAnalysis.conversation_id == conversation_id)
    )
    analysis = analysis_result.scalar_one_or_none()

    # If HTMX request, return just the detail panel
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "conversations/_detail.html",
            {
                "request": request,
                "conversation": conversation,
                "messages": messages,
                "analysis": analysis,
            },
        )

    return request.app.state.templates.TemplateResponse(
        "conversations/detail.html",
        {
            "request": request,
            "conversation": conversation,
            "messages": messages,
            "analysis": analysis,
        },
    )


@router.patch("/conversations/{conversation_id}/status", response_class=HTMLResponse)
async def update_conversation_status(
    request: Request,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    form = await request.form()
    new_status = form.get("status")
    if new_status not in ("open", "closed", "resolved", "escalated"):
        return HTMLResponse("Invalid status", status_code=400)

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.workspace_id == workspace.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return HTMLResponse("Not found", status_code=404)

    conv.status = new_status
    await db.flush()
    # Return updated status badge
    status_map = {
        "open": ("bg-green-100 text-green-700", "Open"),
        "closed": ("bg-gray-100 text-gray-600", "Closed"),
        "resolved": ("bg-blue-100 text-blue-700", "Resolved"),
        "escalated": ("bg-amber-100 text-amber-700", "Escalated"),
    }
    css, label = status_map.get(new_status, ("bg-gray-100 text-gray-600", new_status))
    return HTMLResponse(
        f'<span id="conv-status-badge" class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium {css}">{label}</span>'
    )
