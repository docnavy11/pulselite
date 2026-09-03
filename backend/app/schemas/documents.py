import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DocumentCreate(BaseModel):
    knowledge_base_id: uuid.UUID
    source_type: str
    source_url: str | None = None
    raw_content: str | None = Field(default=None, max_length=5_000_000)
    title: str | None = Field(default=None, max_length=1_000)
    sync_frequency: str = "weekly"

    @field_validator("source_type", "source_url", "raw_content", "title")
    @classmethod
    def no_null_bytes(cls, v: str | None) -> str | None:
        if v is not None and "\x00" in v:
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
    has_file: bool = False
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

    @model_validator(mode="before")
    @classmethod
    def compute_has_file(cls, data):
        if hasattr(data, "file_path"):
            # ORM object
            data_dict = {k: getattr(data, k) for k in cls.model_fields if hasattr(data, k)}
            data_dict["has_file"] = bool(getattr(data, "file_path", None))
            return data_dict
        if isinstance(data, dict) and "file_path" in data:
            data["has_file"] = bool(data.pop("file_path", None))
        return data


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
