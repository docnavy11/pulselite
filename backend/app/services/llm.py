"""Consolidated LLM client — replaces services/llm/ directory (6 files → 1)."""
from __future__ import annotations

import asyncio
import json as _json
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_INTERNAL_MODEL = settings.INTERNAL_MODEL or "claude-haiku-4-5-20251001"


class BaseLLMClient(ABC):
    @abstractmethod
    async def stream_generate(
        self, messages: list[dict], model: str, temperature: float = 0.3, max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def generate(
        self, messages: list[dict], model: str, temperature: float = 0.3, max_tokens: int = 1000,
    ) -> str: ...

    async def generate_with_tools(
        self, messages: list[dict], model: str, tools: list[dict],
        temperature: float = 0.3, max_tokens: int = 1000,
    ) -> dict[str, Any]:
        content = await self.generate(messages, model, temperature, max_tokens)
        return {"type": "message", "content": content}


class OpenRouterLLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key or settings.AI_API_KEY
        self._base_url = base_url or settings.AI_BASE_URL
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url, timeout=httpx.Timeout(60.0))
        return self._client

    async def stream_generate(self, messages, model, temperature=0.7, max_tokens=1000):
        stream = await self._get_client().chat.completions.create(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, stream=True, stream_options={"include_usage": True},
        )
        usage = None
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                usage = {"prompt_tokens": chunk.usage.prompt_tokens, "completion_tokens": chunk.usage.completion_tokens}
        if usage:
            yield usage

    async def generate(self, messages, model, temperature=0.7, max_tokens=1000):
        from openai import OpenAI
        def _sync_call():
            sync_client = OpenAI(api_key=self._api_key, base_url=self._base_url, timeout=60.0)
            response = sync_client.chat.completions.create(
                model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        return await asyncio.to_thread(_sync_call)

    async def generate_with_tools(self, messages, model, tools, temperature=0.3, max_tokens=1000):
        from openai import OpenAI
        def _sync_call():
            sync_client = OpenAI(api_key=self._api_key, base_url=self._base_url, timeout=60.0)
            return sync_client.chat.completions.create(
                model=model, messages=messages, tools=tools, tool_choice="auto",
                temperature=temperature, max_tokens=max_tokens,
            )
        response = await asyncio.to_thread(_sync_call)
        choice = response.choices[0]
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            call = choice.message.tool_calls[0]
            try:
                args = _json.loads(call.function.arguments)
            except Exception:
                args = {}
            return {"type": "tool_call", "tool_name": call.function.name, "tool_call_id": call.id, "arguments": args}
        return {"type": "message", "content": choice.message.content or ""}


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        from openai import AsyncOpenAI
        kwargs = {"api_key": api_key or settings.AI_API_KEY, "timeout": httpx.Timeout(60.0)}
        resolved = base_url or settings.AI_BASE_URL
        if resolved:
            kwargs["base_url"] = resolved
        self._client = AsyncOpenAI(**kwargs)

    async def stream_generate(self, messages, model="gpt-4o-mini", temperature=0.3, max_tokens=1000):
        stream = await self._client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, stream=True, stream_options={"include_usage": True},
        )
        usage = None
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                usage = {"prompt_tokens": chunk.usage.prompt_tokens, "completion_tokens": chunk.usage.completion_tokens}
        if usage:
            yield usage

    async def generate(self, messages, model="gpt-4o-mini", temperature=0.3, max_tokens=1000):
        response = await self._client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


class AnthropicLLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None):
        import anthropic
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.ANTHROPIC_API_KEY, timeout=httpx.Timeout(60.0),
        )

    async def stream_generate(self, messages, model="claude-sonnet-4-20250514", temperature=0.3, max_tokens=1000):
        system_msg = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)
        async with self._client.messages.stream(
            model=model, messages=chat_messages, system=system_msg,
            temperature=temperature, max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate(self, messages, model="claude-sonnet-4-20250514", temperature=0.3, max_tokens=1000):
        system_msg = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)
        response = await self._client.messages.create(
            model=model, messages=chat_messages, system=system_msg,
            temperature=temperature, max_tokens=max_tokens,
        )
        return response.content[0].text


class GoogleLLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.GOOGLE_AI_API_KEY

    async def stream_generate(self, messages, model="gemini-2.0-flash", temperature=0.3, max_tokens=1000):
        raise NotImplementedError("Google LLM client not yet implemented in v2")
        yield  # make it a generator

    async def generate(self, messages, model="gemini-2.0-flash", temperature=0.3, max_tokens=1000):
        raise NotImplementedError("Google LLM client not yet implemented in v2")


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
    from sqlalchemy import select
    from app.models.organizational import Workspace
    result = await session.execute(select(Workspace.internal_model).where(Workspace.id == workspace_id))
    model = result.scalar_one_or_none()
    return model or DEFAULT_INTERNAL_MODEL
