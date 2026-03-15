from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings
from app.services.llm.base import BaseLLMClient


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        kwargs: dict = {"api_key": api_key or settings.AI_API_KEY}
        resolved_base_url = base_url or settings.AI_BASE_URL
        if resolved_base_url:
            kwargs["base_url"] = resolved_base_url
        self._client = AsyncOpenAI(**kwargs)

    async def stream_generate(
        self,
        messages: list[dict],
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def generate(
        self,
        messages: list[dict],
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
