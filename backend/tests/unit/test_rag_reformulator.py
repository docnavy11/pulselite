import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.id = "cb-1"
    cb.llm_provider = overrides.get("llm_provider", "openrouter")
    cb.llm_model = overrides.get("llm_model", "openai/gpt-4o-mini")
    cb.byoak = overrides.get("byoak", None)
    cb.workspace_id = "ws-1"
    return cb


class TestReformulateQueries:
    @pytest.mark.asyncio
    async def test_returns_three_queries_on_success(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=json.dumps({
            "queries": [
                "How to set up SSO?",
                "SAML configuration guide",
                "Single sign-on setup steps",
            ]
        }))

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries(
                "How do I configure SAML SSO?",
                _make_chatbot(),
            )

        assert len(result) == 3
        assert "SSO" in result[0]
        mock_client.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_workspace_openrouter_key(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1", "q2", "q3"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client) as mock_get:
            await reformulate_queries(
                "test query",
                _make_chatbot(),
                openrouter_key="sk-ws-key",
            )

        mock_get.assert_called_once_with("openrouter", api_key="sk-ws-key", base_url=None)

    @pytest.mark.asyncio
    async def test_uses_byoak_when_no_workspace_key(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1", "q2", "q3"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client) as mock_get, \
             patch("app.services.encryption.decrypt_api_key", return_value="decrypted-key"):
            await reformulate_queries(
                "test query",
                _make_chatbot(byoak="encrypted-key", llm_provider="openai"),
            )

        mock_get.assert_called_once_with("openai", api_key="decrypted-key", base_url=None)

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_llm_error(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(side_effect=Exception("LLM timeout"))

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_invalid_json(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value="not json at all")

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_missing_queries_key(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"rephrased": ["q1"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_fewer_than_three_queries(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == ["q1"]

    @pytest.mark.asyncio
    async def test_system_prompt_includes_optimization_instruction(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1", "q2", "q3"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            await reformulate_queries("How do I login?", _make_chatbot())

        call_kwargs = mock_client.generate.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages") or call_kwargs[0][0]
        system_msg = [m for m in messages if m["role"] == "system"][0]
        assert "alternative" in system_msg["content"].lower() or "rephras" in system_msg["content"].lower()
        user_msg = [m for m in messages if m["role"] == "user"][0]
        assert "How do I login?" in user_msg["content"]

    @pytest.mark.asyncio
    async def test_filters_whitespace_only_queries(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["valid query", "  ", ""]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == ["valid query"]

    @pytest.mark.asyncio
    async def test_passes_openrouter_base_url(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client) as mock_get:
            await reformulate_queries(
                "test",
                _make_chatbot(),
                openrouter_key="sk-key",
                openrouter_base_url="https://custom.api.com",
            )

        mock_get.assert_called_once_with("openrouter", api_key="sk-key", base_url="https://custom.api.com")

    @pytest.mark.asyncio
    async def test_uses_chatbot_model(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            await reformulate_queries("test", _make_chatbot(llm_model="anthropic/claude-3-haiku"))

        call_kwargs = mock_client.generate.call_args
        assert call_kwargs.kwargs.get("model") == "anthropic/claude-3-haiku"
