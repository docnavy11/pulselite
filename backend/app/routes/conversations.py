"""Conversation routes — list and detail views."""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.conversation_service import list_conversations, get_conversation, get_messages

router = APIRouter()


@router.get("/conversations", response_class=HTMLResponse)
async def conversation_list(
    request: Request,
    status: str | None = Query(None),
    chatbot_id: uuid.UUID | None = Query(None),
    outcome: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    conversations = await list_conversations(
        db, workspace.id, status_filter=status, chatbot_id=chatbot_id, outcome_filter=outcome,
    )
    return request.app.state.templates.TemplateResponse("conversations/list.html", {
        "request": request, "conversations": conversations,
    })


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
async def conversation_detail(
    request: Request, conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    conversation = await get_conversation(db, conversation_id, workspace.id)
    messages = await get_messages(db, conversation_id, workspace.id)
    return request.app.state.templates.TemplateResponse("conversations/detail.html", {
        "request": request, "conversation": conversation, "messages": messages,
    })
