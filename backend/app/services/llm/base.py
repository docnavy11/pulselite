from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


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
