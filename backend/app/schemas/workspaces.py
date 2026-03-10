import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class WorkspaceCreate(BaseModel):
    name: str
    slug: str

    @field_validator("name", "slug")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    timezone: str
    primary_language: str
    created_at: datetime

    model_config = {"from_attributes": True}
