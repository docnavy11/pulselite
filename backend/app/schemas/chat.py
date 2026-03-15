import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    chatbot_id: uuid.UUID
    message: str
    conversation_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None


class ChatEvent(BaseModel):
    type: str  # token | done | error | action
    data: Any
    confidence_score: float | None = None
    confidence_avg: float | None = None
    escalated: bool = False
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    sources: list[dict] = []


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_type: str
    author_type: str
    content: str | None
    confidence_score: float | None
    is_fallback: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    chatbot_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    assignee_id: uuid.UUID | None
    status: str
    priority: str
    channel: str
    confidence_avg: float | None
    outcome: str | None
    ai_participated: bool
    autonomous_resolved: bool
    topics: list[str] | None = None
    last_message_preview: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
