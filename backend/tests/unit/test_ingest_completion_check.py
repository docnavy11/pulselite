"""Tests for the ingest_document completion check logic."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


class TestCheckAndTriggerAutoconfig:
    @pytest.mark.asyncio
    async def test_fires_autoconfig_when_all_docs_terminal(self):
        """When all KB docs are indexed/failed, and chatbot is 'crawling',
        the atomic update should succeed and fire the autoconfig task."""
        from app.workers.tasks.ingest_document import _check_and_trigger_autoconfig

        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        chatbot_id = uuid.uuid4()

        # Simulate: doc lookup → kb lookup → pending count = 0 → update returns chatbot_id
        session = AsyncMock()

        doc_row = MagicMock()
        doc_row.knowledge_base_id = kb_id

        kb_row = MagicMock()
        kb_row.chatbot_id = chatbot_id

        # sequence of execute() calls: doc, kb, count, update
        execute_results = [
            MagicMock(one_or_none=MagicMock(return_value=doc_row)),   # doc lookup
            MagicMock(one_or_none=MagicMock(return_value=kb_row)),    # kb lookup
            MagicMock(scalar_one=MagicMock(return_value=0)),           # pending count = 0
            MagicMock(scalar_one_or_none=MagicMock(return_value=chatbot_id)),  # update wins
        ]
        session.execute = AsyncMock(side_effect=execute_results)
        session.commit = AsyncMock()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workers.tasks.ingest_document.async_session_factory", return_value=mock_session_ctx), \
             patch("app.workers.tasks.ingest_document.engine") as mock_engine, \
             patch("app.workers.tasks.ingest_document.run_autoconfig_for_chatbot") as mock_task:
            mock_engine.dispose = AsyncMock()
            await _check_and_trigger_autoconfig(doc_id)

        mock_task.delay.assert_called_once_with(str(chatbot_id))

    @pytest.mark.asyncio
    async def test_does_not_fire_when_docs_still_pending(self):
        """When pending doc count > 0, autoconfig task is not fired."""
        from app.workers.tasks.ingest_document import _check_and_trigger_autoconfig

        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        chatbot_id = uuid.uuid4()

        session = AsyncMock()

        doc_row = MagicMock()
        doc_row.knowledge_base_id = kb_id

        kb_row = MagicMock()
        kb_row.chatbot_id = chatbot_id

        execute_results = [
            MagicMock(one_or_none=MagicMock(return_value=doc_row)),
            MagicMock(one_or_none=MagicMock(return_value=kb_row)),
            MagicMock(scalar_one=MagicMock(return_value=3)),  # 3 pending docs
        ]
        session.execute = AsyncMock(side_effect=execute_results)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workers.tasks.ingest_document.async_session_factory", return_value=mock_session_ctx), \
             patch("app.workers.tasks.ingest_document.engine") as mock_engine, \
             patch("app.workers.tasks.ingest_document.run_autoconfig_for_chatbot") as mock_task:
            mock_engine.dispose = AsyncMock()
            await _check_and_trigger_autoconfig(doc_id)

        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_kb_has_no_chatbot(self):
        """When KnowledgeBase.chatbot_id is None, no autoconfig is fired."""
        from app.workers.tasks.ingest_document import _check_and_trigger_autoconfig

        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()

        session = AsyncMock()

        doc_row = MagicMock()
        doc_row.knowledge_base_id = kb_id

        kb_row = MagicMock()
        kb_row.chatbot_id = None  # no chatbot

        execute_results = [
            MagicMock(one_or_none=MagicMock(return_value=doc_row)),
            MagicMock(one_or_none=MagicMock(return_value=kb_row)),
        ]
        session.execute = AsyncMock(side_effect=execute_results)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workers.tasks.ingest_document.async_session_factory", return_value=mock_session_ctx), \
             patch("app.workers.tasks.ingest_document.engine") as mock_engine, \
             patch("app.workers.tasks.ingest_document.run_autoconfig_for_chatbot") as mock_task:
            mock_engine.dispose = AsyncMock()
            await _check_and_trigger_autoconfig(doc_id)

        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_atomic_update_loss_does_not_fire(self):
        """When another task wins the atomic update, this task does not fire autoconfig."""
        from app.workers.tasks.ingest_document import _check_and_trigger_autoconfig

        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        chatbot_id = uuid.uuid4()

        session = AsyncMock()

        doc_row = MagicMock()
        doc_row.knowledge_base_id = kb_id
        kb_row = MagicMock()
        kb_row.chatbot_id = chatbot_id

        execute_results = [
            MagicMock(one_or_none=MagicMock(return_value=doc_row)),
            MagicMock(one_or_none=MagicMock(return_value=kb_row)),
            MagicMock(scalar_one=MagicMock(return_value=0)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # update lost the race
        ]
        session.execute = AsyncMock(side_effect=execute_results)
        session.commit = AsyncMock()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workers.tasks.ingest_document.async_session_factory", return_value=mock_session_ctx), \
             patch("app.workers.tasks.ingest_document.engine") as mock_engine, \
             patch("app.workers.tasks.ingest_document.run_autoconfig_for_chatbot") as mock_task:
            mock_engine.dispose = AsyncMock()
            await _check_and_trigger_autoconfig(doc_id)

        mock_task.delay.assert_not_called()
