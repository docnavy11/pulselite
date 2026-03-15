import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_openrouter_client_streams_tokens():
    """OpenRouterLLMClient.stream_generate yields tokens via OpenAI SDK with custom base_url."""
    from app.services.llm.openrouter_client import OpenRouterLLMClient

    client = OpenRouterLLMClient(api_key="sk-or-test")

    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock()]
    mock_chunk.choices[0].delta.content = "hello"
    mock_chunk.usage = None

    # Final chunk with usage metadata
    mock_final = MagicMock()
    mock_final.choices = []
    mock_final.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    async def fake_stream():
        yield mock_chunk
        yield mock_final

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=fake_stream())

    with patch("app.services.llm.openrouter_client.AsyncOpenAI", return_value=mock_openai):
        tokens = []
        async for token in client.stream_generate(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-4o-mini",
        ):
            tokens.append(token)

    assert tokens == ["hello", {"prompt_tokens": 10, "completion_tokens": 5}]


def test_get_llm_client_openrouter():
    """get_llm_client('openrouter') returns an OpenRouterLLMClient."""
    from app.services.llm import get_llm_client
    from app.services.llm.openrouter_client import OpenRouterLLMClient

    client = get_llm_client("openrouter", api_key="sk-or-test")
    assert isinstance(client, OpenRouterLLMClient)
