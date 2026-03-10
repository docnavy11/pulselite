from app.services.llm.base import BaseLLMClient
from app.services.llm.openai_client import OpenAILLMClient
from app.services.llm.anthropic_client import AnthropicLLMClient
from app.services.llm.google_client import GoogleLLMClient
from app.services.llm.openrouter_client import OpenRouterLLMClient


def get_llm_client(provider: str, api_key: str | None = None) -> BaseLLMClient:
    match provider:
        case "openai":
            return OpenAILLMClient(api_key=api_key)
        case "anthropic":
            return AnthropicLLMClient(api_key=api_key)
        case "google":
            return GoogleLLMClient(api_key=api_key)
        case "openrouter":
            return OpenRouterLLMClient(api_key=api_key)
        case _:
            raise ValueError(f"Unsupported LLM provider: {provider}")
