import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.id = "cb-1"
    cb.llm_provider = overrides.get("llm_provider", "openrouter")
    cb.llm_model = overrides.get("llm_model", "openai/gpt-4o-mini")
    cb.temperature = overrides.get("temperature", 0.7)
    cb.max_tokens = overrides.get("max_tokens", 1024)
    cb.byoak = overrides.get("byoak", None)
    cb.workspace_id = "ws-1"
    return cb


class TestStreamResponse:
    @pytest.mark.asyncio
    async def test_streams_tokens_from_llm_client(self):
        from app.services.rag.generator import stream_response

        async def fake_stream(**kwargs):
            yield "Hello"
            yield " world"
            yield {"prompt_tokens": 10, "completion_tokens": 5}

        mock_client = MagicMock()
        mock_client.stream_generate = fake_stream

        with patch("app.services.rag.generator.get_llm_client", return_value=mock_client):
            tokens = []
            async for item in stream_response(
                [{"role": "user", "content": "hi"}],
                _make_chatbot(),
            ):
                tokens.append(item)

        assert tokens == ["Hello", " world", {"prompt_tokens": 10, "completion_tokens": 5}]

    @pytest.mark.asyncio
    async def test_uses_workspace_openrouter_key_when_provided(self):
        from app.services.rag.generator import stream_response

        async def fake_stream(**kwargs):
            yield "ok"

        mock_client = MagicMock()
        mock_client.stream_generate = fake_stream

        with patch("app.services.rag.generator.get_llm_client", return_value=mock_client) as mock_get:
            async for _ in stream_response(
                [{"role": "user", "content": "hi"}],
                _make_chatbot(),
                openrouter_key="sk-ws-key",
            ):
                pass

        mock_get.assert_called_once_with("openrouter", api_key="sk-ws-key", base_url=None)

    @pytest.mark.asyncio
    async def test_uses_byoak_when_no_workspace_key(self):
        from app.services.rag.generator import stream_response

        async def fake_stream(**kwargs):
            yield "ok"

        mock_client = MagicMock()
        mock_client.stream_generate = fake_stream

        with patch("app.services.rag.generator.get_llm_client", return_value=mock_client) as mock_get, \
             patch("app.services.encryption.decrypt_api_key", return_value="decrypted-key"):
            async for _ in stream_response(
                [{"role": "user", "content": "hi"}],
                _make_chatbot(byoak="encrypted-key", llm_provider="openai"),
            ):
                pass

        mock_get.assert_called_once_with("openai", api_key="decrypted-key", base_url=None)

    @pytest.mark.asyncio
    async def test_byoak_decrypt_failure_falls_back_to_none(self):
        """When BYOAK decryption fails, api_key stays None (uses platform key)."""
        from app.services.rag.generator import stream_response

        async def fake_stream(**kwargs):
            yield "ok"

        mock_client = MagicMock()
        mock_client.stream_generate = fake_stream

        with patch("app.services.rag.generator.get_llm_client", return_value=mock_client) as mock_get, \
             patch("app.services.encryption.decrypt_api_key", side_effect=Exception("bad key")):
            async for _ in stream_response(
                [{"role": "user", "content": "hi"}],
                _make_chatbot(byoak="bad-encrypted-key", llm_provider="openai"),
            ):
                pass

        # Falls back to chatbot.llm_provider with api_key=None
        mock_get.assert_called_once_with("openai", api_key=None, base_url=None)

    @pytest.mark.asyncio
    async def test_passes_chatbot_temperature_and_max_tokens(self):
        from app.services.rag.generator import stream_response

        captured_kwargs = {}

        async def fake_stream(**kwargs):
            captured_kwargs.update(kwargs)
            yield "ok"

        mock_client = MagicMock()
        mock_client.stream_generate = fake_stream

        with patch("app.services.rag.generator.get_llm_client", return_value=mock_client):
            async for _ in stream_response(
                [{"role": "user", "content": "hi"}],
                _make_chatbot(temperature=0.3, max_tokens=512),
            ):
                pass

        assert captured_kwargs["temperature"] == 0.3
        assert captured_kwargs["max_tokens"] == 512
