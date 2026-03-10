import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class ArticleCreate(BaseModel):
    knowledge_base_id: uuid.UUID | None = None
    collection_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    body: str | None = None
    slug: str | None = None
    language: str = "en"

    @field_validator("title", "slug", "language")
    @classmethod
    def no_null_bytes(cls, v: str | None) -> str | None:
        if v is not None and "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v


class ArticleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    body: str | None = None
    slug: str | None = None
    collection_id: uuid.UUID | None = None
    language: str | None = None

    @field_validator("title", "language", "slug")
    @classmethod
    def no_null_bytes_update(cls, v: str | None) -> str | None:
        if v is not None and "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v


class ArticleResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID | None
    collection_id: uuid.UUID | None
    author_id: uuid.UUID | None
    title: str
    description: str | None
    body: str | None
    slug: str | None
    state: str
    is_ai_drafted: bool
    views_count: int
    helpful_count: int
    not_helpful_count: int
    language: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
