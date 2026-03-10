# backend/app/schemas/crawl.py
import uuid
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator


class CrawlRequest(BaseModel):
    url: str
    max_pages: int
    knowledge_base_id: Optional[uuid.UUID] = None

    @field_validator("max_pages")
    @classmethod
    def max_pages_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_pages must be at least 1")
        return v

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


class CrawlJobStatusResponse(BaseModel):
    job_id: str
    kb_id: str
    status: str
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    over_limit: bool
    limit: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
