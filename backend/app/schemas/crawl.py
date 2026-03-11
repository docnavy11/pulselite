# backend/app/schemas/crawl.py
import uuid
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = Field(..., ge=1, le=500)
    knowledge_base_id: Optional[uuid.UUID] = None
    chatbot_id: Optional[uuid.UUID] = None

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must be http or https")
        if not parsed.netloc:
            raise ValueError("URL must include a valid host")
        return v


class CrawlResponse(BaseModel):
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int
    over_limit: bool
    limit: int


class CrawlJobSummary(BaseModel):
    job_id: str
    status: str
    root_url: str
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    docs_indexed: int
    created_at: str
    completed_at: Optional[str] = None


class CrawlJobStatusResponse(BaseModel):
    job_id: str
    kb_id: str
    status: str
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    docs_indexed: int
    docs_total: int
    docs_failed: int
    stalled: bool
    over_limit: bool
    limit: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
