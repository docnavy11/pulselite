import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class KnowledgeBaseCreate(BaseModel):
    chatbot_id: uuid.UUID | None = None
    name: str
    kb_type: str = "general"

    @field_validator("name")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v


class KnowledgeBaseResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    chatbot_id: uuid.UUID | None
    name: str
    kb_type: str
    created_at: datetime

    model_config = {"from_attributes": True}
