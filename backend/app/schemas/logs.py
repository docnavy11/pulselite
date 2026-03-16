"""Response schemas for the logs endpoints."""
from typing import Optional
from pydantic import BaseModel


class CrawlRunLogItem(BaseModel):
    job_id: str
    chatbot_id: Optional[str] = None
    chatbot_name: Optional[str] = None
    root_url: str
    status: str
    phase: Optional[str] = None
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    docs_indexed: int
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class CrawlRunLogResponse(BaseModel):
    items: list[CrawlRunLogItem]
    total: int


class DocumentLogItem(BaseModel):
    id: str
    title: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str
    status: str
    chunk_count: int
    last_indexed_at: Optional[str] = None
    error_message: Optional[str] = None
    ingestion_steps: Optional[list] = None
    knowledge_base_id: str
    knowledge_base_name: str
    chatbot_id: Optional[str] = None
    chatbot_name: Optional[str] = None


class DocumentLogResponse(BaseModel):
    items: list[DocumentLogItem]
    total: int


class AnalysisRunLogItem(BaseModel):
    id: str
    conversation_id: str
    chatbot_id: Optional[str] = None
    chatbot_name: Optional[str] = None
    contact_name: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    intent_primary: Optional[str] = None
    outcome_category: Optional[str] = None
    topics: Optional[list[str]] = None
    summary: Optional[str] = None
    llm_model: str
    processing_ms: Optional[int] = None
    created_at: str


class AnalysisRunLogResponse(BaseModel):
    items: list[AnalysisRunLogItem]
    total: int


class RetrievalLogItem(BaseModel):
    id: str
    chatbot_id: str
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    query: str
    confidence_score: float
    confidence_avg: Optional[float] = None
    chunk_count: Optional[int] = None
    reranked: bool
    escalated: bool
    response_generated: bool
    retrieval_ms: Optional[int] = None
    generation_ms: Optional[int] = None
    created_at: str


class RetrievalLogResponse(BaseModel):
    items: list[RetrievalLogItem]
    total: int
