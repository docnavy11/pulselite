import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ResolutionStatsResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    chatbot_id: uuid.UUID | None
    period_date: date
    total_conversations: int
    autonomously_resolved: int
    escalated_to_human: int
    abandoned: int
    avg_confidence_score: float | None
    knowledge_velocity: float | None
    documentation_debt: int | None

    model_config = {"from_attributes": True}


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


class LeadScoreResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    contact_id: uuid.UUID
    conversation_id: uuid.UUID
    score: int
    tier: str | None
    crm_pushed: bool
    scored_at: datetime

    model_config = {"from_attributes": True}


class IntelligenceSignalResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    contact_id: uuid.UUID | None
    signal_type: str
    confidence: float | None
    payload: dict
    actioned: bool
    dismissed: bool
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
    lead_intent: str | None
    feature_requests: list[str] | None
    bug_reports: list[str] | None
    competitor_mentions: list[str] | None
    expansion_signals: list[str] | None
    churn_signals: list[str] | None
    topics: list[str] | None
    customer_effort_score: float | None
    summary: str | None
    action_items: list[str] | None
    llm_model: str
    processing_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
