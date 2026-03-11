from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any


class BaseLLMClient(ABC):
    @abstractmethod
    async def stream_generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str: ...

    async def generate_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """
        Non-streaming call with tool definitions.
        Returns either:
          {"type": "message", "content": "..."}
          {"type": "tool_call", "tool_name": "...", "tool_call_id": "...", "arguments": {...}}
        Default implementation falls back to plain generate (no tool support).
        """
        content = await self.generate(messages, model, temperature, max_tokens)
        return {"type": "message", "content": content}
