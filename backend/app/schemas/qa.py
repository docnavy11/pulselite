import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GenerateQARequest(BaseModel):
    count: int = Field(ge=1, le=50, default=10)


class CreateQAPairRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class QAPairUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None


class QAPairResponse(BaseModel):
    id: uuid.UUID
    chatbot_id: uuid.UUID
    question: str
    answer: str | None
    suggested_answer: str | None
    status: str
    confidence_score: float | None
    escalated: bool
    sources: list[dict] | None
    is_edited: bool
    kb_document_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QAPairListResponse(BaseModel):
    items: list[QAPairResponse]
    total: int
