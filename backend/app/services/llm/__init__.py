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


class AgentSDKLLMClient(BaseLLMClient):
    """Claude through the Claude Agent SDK — no API key, no proxy.

    The SDK is Claude Code as a library: it authenticates the way the CLI does,
    so a logged-in CLI on the host is the whole credential story. Two
    consequences matter at the call site:

    - It is a conversation harness, not a completions endpoint. It has no
      temperature and no max_tokens, so both arguments are accepted and ignored.
    - Every call spawns a CLI subprocess. Measured on this host 2026-09-16: 3.5s
      for a one-line JSON reply. It is not the client for a hot path.

    Every built-in tool is disabled and `setting_sources=[]` keeps the host's
    settings, CLAUDE.md and MCP servers out of the conversation.
    """

    # Named explicitly as well as omitted from `allowed_tools`: the whitelist
    # alone has been observed not to close the surface.
    BUILTINS = [
        "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "BashOutput",
        "KillShell", "Glob", "Grep", "WebSearch", "WebFetch", "Task", "TodoWrite",
        "SlashCommand", "ToolSearch", "ExitPlanMode", "EnterPlanMode", "Artifact",
        "Skill", "Workflow", "AskUserQuestion",
    ]

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        # api_key/base_url are part of the shared factory signature; the SDK uses
        # the CLI's own credentials and ignores both.
        self._model = settings.INTERNAL_MODEL or DEFAULT_INTERNAL_MODEL

    @staticmethod
    def _split(messages: list[dict]) -> tuple[str, str]:
        """Return (system_prompt, prompt) from an OpenAI-style message list."""
        system = "\n\n".join(
            str(m.get("content") or "") for m in messages if m.get("role") == "system"
        )
        turns = [m for m in messages if m.get("role") != "system"]
        if len(turns) == 1 and turns[0].get("role") == "user":
            return system, str(turns[0].get("content") or "")
        prompt = "\n\n".join(
            f"{'Assistant' if m.get('role') == 'assistant' else 'User'}: "
            f"{str(m.get('content') or '')}"
            for m in turns
        )
        return system, prompt

    def _options(self, system_prompt: str, model: str | None):
        from claude_agent_sdk import ClaudeAgentOptions
        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "allowed_tools": [],
            "disallowed_tools": self.BUILTINS,
            "setting_sources": [],
            "permission_mode": "bypassPermissions",
            "max_turns": 1,
            # The subprocess must not inherit a conflicting credential: an
            # ANTHROPIC_API_KEY in the environment takes precedence over the
            # CLI login, and a placeholder value (".env" ships one) fails the
            # call with "Invalid API key". Blanking these restores the login.
            "env": {
                "ANTHROPIC_API_KEY": "",
                "ANTHROPIC_AUTH_TOKEN": "",
                "ANTHROPIC_BASE_URL": "",
            },
        }
        if system_prompt:
            kwargs["system_prompt"] = system_prompt
        return ClaudeAgentOptions(**kwargs)

    async def _run(self, messages: list[dict], model: str | None):
        """Yield ('text', delta) as it arrives, then ('usage', dict) at the end."""
        from claude_agent_sdk import (AssistantMessage, ClaudeSDKClient,
                                      ResultMessage, TextBlock)
        system_prompt, prompt = self._split(messages)
        async with ClaudeSDKClient(self._options(system_prompt, model)) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            yield "text", block.text
                elif isinstance(msg, ResultMessage):
                    if msg.is_error:
                        raise RuntimeError(
                            f"Agent SDK returned an error: {msg.result or msg.subtype}"
                        )
                    raw = msg.usage or {}
                    yield "usage", {
                        "prompt_tokens": raw.get("input_tokens", 0),
                        "completion_tokens": raw.get("output_tokens", 0),
                    }

    async def generate(self, messages, model=None, temperature=0.3, max_tokens=1000):
        parts: list[str] = []
        async for kind, value in self._run(messages, model):
            if kind == "text":
                parts.append(value)
        return "".join(parts)

    async def stream_generate(self, messages, model=None, temperature=0.3, max_tokens=1000):
        async for kind, value in self._run(messages, model):
            yield value

    async def generate_with_tools(self, messages, model=None, tools=None, temperature=0.3, max_tokens=1000):
        """No tool calling yet — returns a plain message, loudly.

        The SDK does support tools, but only as MCP servers, so the OpenAI-style
        `tools` schemas used by chatbot actions would have to be translated
        first. Until that exists, a chatbot on this provider never fires an
        action; it answers in text. Logged rather than swallowed so the
        behaviour is visible in the admin log viewer.
        """
        if tools:
            logger.warning(
                "agentsdk: %d tool(s) offered but tool calling is not implemented; "
                "returning a text answer and firing no action", len(tools),
            )
        return await super().generate_with_tools(messages, model, tools or [], temperature, max_tokens)


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
        case "agentsdk":
            return AgentSDKLLMClient()
        case _:
            raise ValueError(f"Unsupported LLM provider: {provider}")


def get_internal_client() -> BaseLLMClient:
    """Client for PulseLight's own LLM calls — autoconfig, gap analysis, judging.

    Distinct from a workspace's chatbot provider, which the customer chooses and
    pays for. Defaults to the Agent SDK, which needs no key of its own.
    """
    return get_llm_client(settings.INTERNAL_PROVIDER or "agentsdk")


async def get_internal_model(session, workspace_id: uuid.UUID) -> str:
    from sqlalchemy import select
    from app.models.organizational import Workspace
    result = await session.execute(select(Workspace.internal_model).where(Workspace.id == workspace_id))
    model = result.scalar_one_or_none()
    return model or DEFAULT_INTERNAL_MODEL
