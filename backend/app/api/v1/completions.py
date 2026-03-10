import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import Chatbot
from app.services import api_key_service
from app.services.rag.engine import RAGResult, process_query
from app.services import conversation_service

router = APIRouter(tags=["completions"])
security = HTTPBearer()


class CompletionRequest(BaseModel):
    chatbot_id: uuid.UUID
    message: str
    conversation_id: uuid.UUID | None = None


class CompletionResponse(BaseModel):
    response: str
    conversation_id: uuid.UUID
    confidence: float


@router.post("/chat/completions", response_model=CompletionResponse)
async def create_completion(
    body: CompletionRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    api_key = await api_key_service.validate_api_key(db, credentials.credentials)

    result = await db.execute(
        select(Chatbot).where(Chatbot.id == body.chatbot_id, Chatbot.is_active == True)  # noqa: E712
    )
    chatbot = result.scalar_one_or_none()
    if chatbot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chatbot not found")

    if chatbot.workspace_id != api_key.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key does not belong to this workspace")

    conversation_id = body.conversation_id
    if conversation_id is None:
        conversation = await conversation_service.create_conversation(db, chatbot.workspace_id, chatbot.id)
        conversation_id = conversation.id

    await conversation_service.add_message(
        db,
        conversation_id,
        chatbot.workspace_id,
        content=body.message,
        author_type="contact",
        message_type="incoming",
    )

    full_response = ""
    confidence = 0.0

    async for item in process_query(db, body.message, chatbot, conversation_id):
        if isinstance(item, RAGResult):
            confidence = item.confidence_score
            continue
        full_response += item

    await conversation_service.add_message(
        db,
        conversation_id,
        chatbot.workspace_id,
        content=full_response,
        author_type="bot",
        message_type="outgoing",
        confidence_score=confidence,
    )

    return CompletionResponse(
        response=full_response,
        conversation_id=conversation_id,
        confidence=confidence,
    )
