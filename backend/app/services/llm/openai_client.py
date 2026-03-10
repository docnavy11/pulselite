from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings
from app.services.llm.base import BaseLLMClient


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)

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
