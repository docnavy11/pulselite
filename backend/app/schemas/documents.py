import uuid
from datetime import datetime
from typing import Literal, Optional

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
    metadata_: dict = {}
    error_message: Optional[str] = None
    ingestion_steps: Optional[list] = None

    model_config = {"from_attributes": True}


class ChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content: str
    heading_path: str | None
    token_count: int | None

    model_config = {"from_attributes": True}


class IngestionStepResponse(BaseModel):
    step: str
    status: str
    started_at: str | None = None
    duration_ms: int | None = None
    detail: str | None = None
    error: str | None = None


class DocumentContentResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    source_type: str
    source_url: str | None
    status: str
    error_message: str | None
    char_count: int
    chunk_count: int
    raw_content: str | None
    chunks: list[ChunkResponse]
    ingestion_steps: list[IngestionStepResponse] | None = None
    last_indexed_at: datetime | None = None

    model_config = {"from_attributes": True}
