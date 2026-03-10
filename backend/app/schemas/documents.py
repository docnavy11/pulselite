import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class DocumentCreate(BaseModel):
    knowledge_base_id: uuid.UUID
    source_type: str
    source_url: str | None = None
    raw_content: str | None = None
    title: str | None = None
    sync_frequency: str = "weekly"

    @field_validator("source_type")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v


class DocumentUpdate(BaseModel):
    sync_frequency: Literal["manual", "daily", "weekly", "monthly"] | None = None
    title: str | None = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_type: str
    source_url: str | None
    file_path: str | None
    title: str | None
    status: str
    chunk_count: int
    last_indexed_at: datetime | None
    sync_frequency: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
