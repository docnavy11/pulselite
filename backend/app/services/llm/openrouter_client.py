from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings
from app.services.llm.base import BaseLLMClient

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.OPENROUTER_API_KEY

    def _get_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self._api_key, base_url=OPENROUTER_BASE_URL)

    async def stream_generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        stream = await self._get_client().chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
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
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        response = await self._get_client().chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
