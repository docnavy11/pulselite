import logging
from collections.abc import AsyncGenerator

from app.models.knowledge import Chatbot
from app.services.llm import get_llm_client

logger = logging.getLogger(__name__)


async def stream_response(
    messages: list[dict],
    chatbot: Chatbot,
    openrouter_key: str | None = None,
    openrouter_base_url: str | None = None,
) -> AsyncGenerator[str, None]:
    # Workspace OpenRouter key takes priority over chatbot-level byoak
    api_key = openrouter_key
    if api_key is None and chatbot.byoak:
        try:
            from app.services.encryption import decrypt_api_key
            api_key = decrypt_api_key(chatbot.byoak)
        except Exception:
            logger.warning(f"Failed to decrypt BYOK key for chatbot {chatbot.id}, using platform key")

    # If workspace OpenRouter key provided, always use openrouter provider
    provider = "openrouter" if openrouter_key else chatbot.llm_provider
    client = get_llm_client(provider, api_key=api_key, base_url=openrouter_base_url)
    async for token in client.stream_generate(  # type: ignore[misc]
        messages=messages,
        model=chatbot.llm_model,
        temperature=chatbot.temperature,
        max_tokens=chatbot.max_tokens,
    ):
        yield token
