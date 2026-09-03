import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _strip_null_bytes(v: str) -> str:
    """Remove null bytes that would cause PostgreSQL errors."""
    return v.replace("\x00", "") if isinstance(v, str) else v


DANGEROUS_CSS_PATTERNS = [
    r'expression\s*\(',
    r'javascript\s*:',
    r'@import',
    r'url\s*\(',
    r'behavior\s*:',
    r'-moz-binding',
]


def sanitize_css(css: str) -> str:
    """Strip dangerous CSS patterns that could be used for data exfiltration or XSS."""
    if not css:
        return css
    for pattern in DANGEROUS_CSS_PATTERNS:
        css = re.sub(pattern, '', css, flags=re.IGNORECASE)
    return css


class WidgetConfig(BaseModel):
    primary_color: str = Field(default="#6366f1", max_length=50)
    position: str = Field(default="bottom-right", max_length=50)
    welcome_message: str = Field(default="Hi! How can I help you?", max_length=5_000)
    avatar_url: str | None = Field(default=None, max_length=2_000)
    launcher_text: str = Field(default="Chat with us", max_length=200)
    quick_replies: list[str] = []
    lead_capture_enabled: bool = False
    lead_capture_fields: list[str] = ["name", "email"]
    gdpr_consent_enabled: bool = False
    gdpr_consent_text: str = (
        "By continuing, you agree to our Privacy Policy and consent to this chat being stored for support purposes."
    )
    allowed_domains: list[str] = Field(default_factory=list)
    auto_open_delay: int | None = None  # seconds; None = don't auto-open
    persist_conversation: bool = False
    custom_css: Optional[str] = None

    @field_validator(
        "primary_color",
        "position",
        "welcome_message",
        "launcher_text",
        "gdpr_consent_text",
        "custom_css",
        mode="before",
    )
    @classmethod
    def strip_null_bytes(cls, v: object) -> object:
        return _strip_null_bytes(v) if isinstance(v, str) else v

    @field_validator("custom_css", mode="after")
    @classmethod
    def sanitize_custom_css(cls, v: object) -> object:
        return sanitize_css(v) if isinstance(v, str) else v

    @field_validator("quick_replies", "lead_capture_fields", "allowed_domains", mode="before")
    @classmethod
    def strip_null_bytes_list(cls, v: object) -> object:
        if isinstance(v, list):
            return [_strip_null_bytes(item) if isinstance(item, str) else item for item in v]
        return v


class WidgetConfigResponse(BaseModel):
    chatbot_id: str
    workspace_id: str
    display_name: str
    avatar_url: str | None
    widget_config: WidgetConfig
    # Flattened here for direct consumption by widget/src/index.ts and /chat page
    primary_color: str = "#6366f1"
    position: str = "bottom-right"
    welcome_message: str = "Hi! How can I help you?"
    launcher_text: str = "Chat with us"
    quick_replies: list[str] = []
    lead_capture_enabled: bool = False
    lead_capture_fields: list[str] = ["name", "email"]
    gdpr_consent_enabled: bool = False
    gdpr_consent_text: str = (
        "By continuing, you agree to our Privacy Policy and consent to this chat being stored for support purposes."
    )
    allowed_domains: list[str] = []
    auto_open_delay: int | None = None
    persist_conversation: bool = False
    custom_css: Optional[str] = None

    model_config = {"from_attributes": True}


class PersonaUpdate(BaseModel):
    system_prompt: str | None = None
    tone: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    language: str | None = None
    auto_detect_language: bool | None = None


class LLMConfigUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieval_top_k: int | None = Field(default=None, ge=1, le=50)
    use_reranking: bool | None = None
    use_hybrid_retrieval: bool | None = None
    byoak: str | None = None
