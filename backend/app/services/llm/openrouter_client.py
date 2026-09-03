from collections.abc import AsyncGenerator

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.services.llm.base import BaseLLMClient

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key or settings.AI_API_KEY
        self._base_url = base_url or settings.AI_BASE_URL
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url, timeout=httpx.Timeout(60.0))
        return self._client

    async def stream_generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str | dict, None]:
        stream = await self._get_client().chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        usage = None
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                usage = {"prompt_tokens": chunk.usage.prompt_tokens, "completion_tokens": chunk.usage.completion_tokens}
        if usage:
            yield usage

    async def generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        import asyncio
        from openai import OpenAI

        # Use synchronous OpenAI client in a thread — the async client's
        # non-streaming calls block the event loop in certain ASGI contexts
        # (e.g. inside SSE generators with EventSourceResponse).
        def _sync_call():
            sync_client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=60.0,
            )
            response = sync_client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        return await asyncio.to_thread(_sync_call)

    async def generate_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> dict:
        import asyncio
        import json as _json
        from openai import OpenAI

        def _sync_call():
            sync_client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=60.0,
            )
            return sync_client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens,
            )

        response = await asyncio.to_thread(_sync_call)
        choice = response.choices[0]
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            call = choice.message.tool_calls[0]
            try:
                args = _json.loads(call.function.arguments)
            except Exception:
                args = {}
            return {
                "type": "tool_call",
                "tool_name": call.function.name,
                "tool_call_id": call.id,
                "arguments": args,
            }
        return {"type": "message", "content": choice.message.content or ""}
