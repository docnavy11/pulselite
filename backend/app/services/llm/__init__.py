from __future__ import annotations

import uuid

from app.services.llm.base import BaseLLMClient
from app.services.llm.openai_client import OpenAILLMClient
from app.services.llm.anthropic_client import AnthropicLLMClient
from app.services.llm.google_client import GoogleLLMClient
from app.services.llm.openrouter_client import OpenRouterLLMClient

from app.config import settings

DEFAULT_INTERNAL_MODEL = settings.INTERNAL_MODEL or "claude-haiku-4-5-20251001"


def get_llm_client(provider: str, api_key: str | None = None, base_url: str | None = None) -> BaseLLMClient:
    match provider:
        case "openai":
            return OpenAILLMClient(api_key=api_key, base_url=base_url)
        case "anthropic":
            return AnthropicLLMClient(api_key=api_key)
        case "google":
            return GoogleLLMClient(api_key=api_key)
        case "openrouter":
            return OpenRouterLLMClient(api_key=api_key, base_url=base_url)
        case _:
            raise ValueError(f"Unsupported LLM provider: {provider}")


async def get_internal_model(session, workspace_id: uuid.UUID) -> str:
    """Resolve the workspace's configured internal model, falling back to the default."""
    from sqlalchemy import select
    from app.models.organizational import Workspace

    result = await session.execute(
        select(Workspace.internal_model).where(Workspace.id == workspace_id)
    )
    model = result.scalar_one_or_none()
    return model or DEFAULT_INTERNAL_MODEL
