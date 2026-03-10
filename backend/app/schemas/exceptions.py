import uuid
from datetime import datetime

from pydantic import BaseModel


class ExceptionConversation(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    chatbot_id: uuid.UUID | None
    chatbot_name: str | None = None
    contact_id: uuid.UUID | None
    contact_name: str | None = None
    contact_email: str | None = None
    escalation_reason: str | None
    confidence_avg: float | None
    status: str
    last_message_preview: str | None = None
    created_at: datetime
    updated_at: datetime


class ExceptionListResponse(BaseModel):
    items: list[ExceptionConversation]
    total: int


class MessageDetail(BaseModel):
    id: uuid.UUID
    content: str | None
    author_type: str
    confidence_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactContext(BaseModel):
    id: uuid.UUID | None = None
    name: str | None = None
    email: str | None = None
    lead_score: int = 0
    lead_tier: str | None = None
    company_name: str | None = None
    previous_conversations_count: int = 0


class ExceptionDetailResponse(BaseModel):
    conversation: ExceptionConversation
    messages: list[MessageDetail]
    contact_context: ContactContext | None = None
    suggested_action: str | None = None


class ExceptionReplyRequest(BaseModel):
    content: str
    resolve: bool = False
