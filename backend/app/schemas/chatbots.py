import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChatbotCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v

    slug: str | None = None
    display_name: str = "Assistant"
    avatar_url: str | None = None
    system_prompt: str | None = None
    tone: str = "professional"
    language: str = "en"
    llm_provider: str = "openrouter"
    llm_model: str = "anthropic/claude-haiku-4-5"
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=32000)
    confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    use_reranking: bool = True
    use_hybrid_retrieval: bool = True
    fallback_type: str = "escalate"
    fallback_message: str | None = None


class ChatbotUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    system_prompt: str | None = None
    tone: str | None = None
    language: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None

    @field_validator("name", "llm_provider", "llm_model", "language", "tone", "display_name")
    @classmethod
    def no_null_bytes_update(cls, v: str | None) -> str | None:
        if v is not None and "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieval_top_k: int | None = Field(default=None, ge=1, le=50)
    use_reranking: bool | None = None
    use_hybrid_retrieval: bool | None = None
    fallback_type: str | None = None
    fallback_message: str | None = None
    is_active: bool | None = None
    welcome_message: str | None = None
    brand_color: str | None = None
    suggested_questions: list[str] | None = None


class ChatbotResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    slug: str | None
    display_name: str
    avatar_url: str | None
    system_prompt: str | None
    tone: str
    language: str
    llm_provider: str
    llm_model: str
    temperature: float
    max_tokens: int
    confidence_threshold: float
    retrieval_top_k: int
    use_reranking: bool
    use_hybrid_retrieval: bool
    fallback_type: str
    fallback_message: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    brand_color: str | None = None
    welcome_message: str | None = None
    suggested_questions: list[str] | None = None

    model_config = {"from_attributes": True}


class AutoConfigRequest(BaseModel):
    knowledge_base_id: uuid.UUID


class AutoConfigResponse(BaseModel):
    name: str
    welcome_message: str | None
    system_prompt: str | None
    suggested_questions: list[str] | None
    fallback_message: str | None
    brand_color: str | None
    tone: str | None
    language: str | None
