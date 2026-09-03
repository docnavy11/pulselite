from collections.abc import AsyncGenerator

import httpx
import anthropic

from app.config import settings
from app.services.llm.base import BaseLLMClient


class AnthropicLLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None):
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.ANTHROPIC_API_KEY,
            timeout=httpx.Timeout(60.0),
        )

    async def stream_generate(
        self,
        messages: list[dict],
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        system_msg = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        async with self._client.messages.stream(
            model=model,
            messages=chat_messages,
            system=system_msg,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate(
        self,
        messages: list[dict],
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        system_msg = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        response = await self._client.messages.create(
            model=model,
            messages=chat_messages,
            system=system_msg,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text
