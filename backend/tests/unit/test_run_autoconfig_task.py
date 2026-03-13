"""Tests for run_autoconfig_for_chatbot Celery task."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRunAutoconfigTask:
    @pytest.mark.asyncio
    async def test_sets_ready_on_success(self):
        """Task sets setup_status='ready' after autoconfig_service.run() succeeds."""
        from app.workers.tasks.run_autoconfig import _run

        chatbot_id = uuid.uuid4()
        kb_id = uuid.uuid4()

        chatbot_mock = MagicMock()
        chatbot_mock.id = chatbot_id
        chatbot_mock.workspace_id = uuid.uuid4()
        chatbot_mock.setup_status = "configuring"
        chatbot_mock.knowledge_bases = [MagicMock(id=kb_id)]

        session = AsyncMock()
        session.commit = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=chatbot_mock)
        session.execute = AsyncMock(return_value=result_mock)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workers.tasks.run_autoconfig.async_session_factory", return_value=mock_session_ctx), \
             patch("app.workers.tasks.run_autoconfig.engine") as mock_engine, \
             patch("app.workers.tasks.run_autoconfig.autoconfig_service") as mock_svc:
            mock_engine.dispose = AsyncMock()
            mock_svc.run = AsyncMock(return_value=chatbot_mock)
            await _run(chatbot_id)

        assert chatbot_mock.setup_status == "ready"
        session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sets_setup_failed_on_mark_failed(self):
        """_mark_setup_failed sets setup_status='setup_failed'."""
        from app.workers.tasks.run_autoconfig import _mark_setup_failed

        chatbot_id = uuid.uuid4()

        chatbot_mock = MagicMock()
        chatbot_mock.setup_status = "configuring"

        session = AsyncMock()
        session.commit = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=chatbot_mock)
        session.execute = AsyncMock(return_value=result_mock)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workers.tasks.run_autoconfig.async_session_factory", return_value=mock_session_ctx), \
             patch("app.workers.tasks.run_autoconfig.engine") as mock_engine:
            mock_engine.dispose = AsyncMock()
            await _mark_setup_failed(chatbot_id)

        assert chatbot_mock.setup_status == "setup_failed"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_chatbot_not_found(self):
        """Task exits silently if chatbot does not exist."""
        from app.workers.tasks.run_autoconfig import _run

        chatbot_id = uuid.uuid4()

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=result_mock)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workers.tasks.run_autoconfig.async_session_factory", return_value=mock_session_ctx), \
             patch("app.workers.tasks.run_autoconfig.engine") as mock_engine, \
             patch("app.workers.tasks.run_autoconfig.autoconfig_service") as mock_svc:
            mock_engine.dispose = AsyncMock()
            await _run(chatbot_id)

        mock_svc.run.assert_not_called()
