import uuid
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class CrawlRequest(BaseModel):
    url: str
    include_paths: list[str] = Field(default_factory=list,
        description="URL path prefixes to include, e.g. ['/blog', '/docs']. Empty = all paths.")
    exclude_paths: list[str] = Field(default_factory=list,
        description="URL path prefixes to exclude, e.g. ['/admin', '/private'].")
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

    @field_validator("include_paths", "exclude_paths")
    @classmethod
    def validate_paths(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("Path list may not exceed 20 entries")
        for entry in v:
            if not entry:
                raise ValueError("Path entries must be non-empty strings")
            if not entry.startswith("/"):
                raise ValueError(f"Path entry must start with '/': {entry!r}")
        return v


class CrawlResponse(BaseModel):
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int


class CrawlJobSummary(BaseModel):
    job_id: str
    status: str
    root_url: str
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    docs_indexed: int
    docs_skipped: int = 0
    created_at: str
    completed_at: Optional[str] = None
    phase: Optional[str] = None
    error_message: Optional[str] = None


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
    docs_skipped: int
    stalled: bool
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    phase: Optional[str] = None
    error_message: Optional[str] = None


class WorkspaceUsageResponse(BaseModel):
    chars_indexed: int
    chars_limit: Optional[int]       # None = unlimited (enterprise)
    chars_remaining: Optional[int]   # None = unlimited
    plan: str
