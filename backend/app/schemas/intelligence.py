import uuid
from datetime import datetime

from pydantic import BaseModel


class RetrievalLogResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    chatbot_id: uuid.UUID
    conversation_id: uuid.UUID | None
    query: str
    confidence_score: float
    confidence_avg: float | None
    escalated: bool
    retrieval_ms: int | None
    generation_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GapEventResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    retrieval_log_id: uuid.UUID
    query: str
    confidence_score: float
    gap_cluster_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationAnalysisResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    sentiment_score: float | None
    sentiment_label: str | None
    intent_primary: str | None
    intent_secondary: list[str] | None
    outcome_category: str | None
    topics: list[str] | None
    summary: str | None
    llm_model: str
    processing_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
