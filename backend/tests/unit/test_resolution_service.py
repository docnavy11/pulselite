import pytest


class TestIsSubstantiveQuery:
    def test_greeting_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("hello") is False
        assert _is_substantive_query("Hi!") is False
        assert _is_substantive_query("hey") is False

    def test_short_message_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("ok") is False
        assert _is_substantive_query("yes") is False
        assert _is_substantive_query("no") is False

    def test_thanks_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("thanks!") is False
        assert _is_substantive_query("Thank you") is False

    def test_identity_question_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("who are you?") is False
        assert _is_substantive_query("what are you?") is False

    def test_real_question_is_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("How do I reset my password?") is True
        assert _is_substantive_query("What are your pricing plans?") is True

    def test_multilingual_greetings(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("bonjour") is False
        assert _is_substantive_query("hallo!") is False
        assert _is_substantive_query("bedankt") is False

    def test_whitespace_and_punctuation(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("  hello!  ") is False
        assert _is_substantive_query("bye?") is False


import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag.engine import RAGResult


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.id = overrides.get("id", uuid.uuid4())
    cb.workspace_id = overrides.get("workspace_id", uuid.uuid4())
    cb.name = "TestBot"
    cb.use_reranking = False
    cb.confidence_threshold = 0.4
    cb.llm_provider = "openrouter"
    cb.llm_model = "openai/gpt-4o-mini"
    return cb


def _make_workspace(**overrides):
    ws = MagicMock()
    ws.id = overrides.get("id", uuid.uuid4())
    ws.openrouter_api_key = overrides.get("openrouter_api_key", None)
    ws.openrouter_base_url = overrides.get("openrouter_base_url", None)
    ws.credit_balance = overrides.get("credit_balance", 1000)
    ws.is_byok = overrides.get("is_byok", False)
    return ws


async def _collect_events(gen):
    events = []
    async for event in gen:
        events.append(event)
    return events


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_creates_conversation_when_none_provided(self):
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        bot_message = MagicMock(id=uuid.uuid4())
        user_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.8, confidence_avg=0.7, escalated=False,
            retrieved_chunk_ids=[], query="test", sources=[],
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Hello!"
            yield {"prompt_tokens": 10, "completion_tokens": 5}

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])
            mock_conv.get_conversation = AsyncMock()

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "How do I login?")
            )

        mock_conv.create_conversation.assert_awaited_once()
        token_events = [e for e in events if e.type == "token"]
        done_events = [e for e in events if e.type == "done"]
        assert len(token_events) == 1
        assert token_events[0].data == "Hello!"
        assert len(done_events) == 1
        assert done_events[0].escalated is False

    @pytest.mark.asyncio
    async def test_escalation_on_low_confidence(self):
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        bot_message = MagicMock(id=uuid.uuid4())
        user_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.2, confidence_avg=0.15, escalated=True,
            retrieved_chunk_ids=[], query="complex question", sources=[],
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "I'm not sure about that."

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "How do I configure advanced SAML SSO?")
            )

        done_event = [e for e in events if e.type == "done"][0]
        assert done_event.escalated is True

    @pytest.mark.asyncio
    async def test_greeting_suppresses_escalation(self):
        """Even if RAG returns low confidence, greetings should not escalate."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        bot_message = MagicMock(id=uuid.uuid4())
        user_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.1, confidence_avg=0.1, escalated=True,
            retrieved_chunk_ids=[], query="hello", sources=[],
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Hi there!"

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "hello!")
            )

        done_event = [e for e in events if e.type == "done"][0]
        assert done_event.escalated is False  # greeting suppresses escalation

    @pytest.mark.asyncio
    async def test_cloud_mode_credit_check(self):
        """Cloud mode with zero credits yields error event."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace(credit_balance=0)
        chatbot = _make_chatbot(workspace_id=ws.id)

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)

        with patch("app.services.resolution_service.is_cloud", return_value=True):
            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "test question here")
            )

        assert len(events) == 1
        assert events[0].type == "error"
        assert "credit" in events[0].data.lower()

    @pytest.mark.asyncio
    async def test_gap_event_recorded_when_original_confidence_low_even_if_retry_succeeds(self):
        """Gap event should be recorded based on original_confidence_low, not escalated."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        user_message = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        # Retry succeeded: escalated=False but original_confidence_low=True
        rag_result = RAGResult(
            confidence_score=0.8, confidence_avg=0.7, escalated=False,
            retrieved_chunk_ids=[], query="How do I configure SAML SSO?",
            sources=[], retried=True, original_confidence_low=True,
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Here's how to configure SAML SSO..."
            yield {"prompt_tokens": 50, "completion_tokens": 20}

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "How do I configure SAML SSO?")
            )

        # Gap event should be recorded (db.add called with GapEvent)
        add_calls = db.add.call_args_list
        from app.models.intelligence import GapEvent as GapEventModel
        gap_adds = [c for c in add_calls if isinstance(c[0][0], GapEventModel)]
        assert len(gap_adds) == 1

    @pytest.mark.asyncio
    async def test_no_gap_event_when_original_confidence_was_fine(self):
        """No gap event when original confidence was above threshold (no retry needed)."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        user_message = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.9, confidence_avg=0.8, escalated=False,
            retrieved_chunk_ids=[], query="What are your pricing plans?",
            sources=[], retried=False, original_confidence_low=False,
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Our pricing plans are..."
            yield {"prompt_tokens": 30, "completion_tokens": 15}

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "What are your pricing plans?")
            )

        # No gap event should be recorded
        add_calls = db.add.call_args_list
        from app.models.intelligence import GapEvent as GapEventModel
        gap_adds = [c for c in add_calls if isinstance(c[0][0], GapEventModel)]
        assert len(gap_adds) == 0

    @pytest.mark.asyncio
    async def test_done_event_includes_sources(self):
        """Done event should include sources from RAGResult."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        user_message = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        sources = [{"index": 1, "title": "FAQ", "url": "https://example.com/faq"}]
        rag_result = RAGResult(
            confidence_score=0.9, confidence_avg=0.8, escalated=False,
            retrieved_chunk_ids=[], query="pricing info",
            sources=sources,
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Here are our pricing plans..."
            yield {"prompt_tokens": 30, "completion_tokens": 15}

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "What are your pricing plans?")
            )

        done_event = [e for e in events if e.type == "done"][0]
        assert done_event.sources == sources

    @pytest.mark.asyncio
    async def test_existing_conversation_reuses_id(self):
        """When conversation_id is provided, no new conversation is created."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        existing_conv_id = uuid.uuid4()
        conversation = MagicMock(id=existing_conv_id)
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        user_message = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.9, confidence_avg=0.8, escalated=False,
            retrieved_chunk_ids=[], query="follow-up question", sources=[],
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Follow-up answer"
            yield {"prompt_tokens": 10, "completion_tokens": 5}

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.get_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "follow-up question",
                               conversation_id=existing_conv_id)
            )

        # Should NOT create a new conversation
        mock_conv.create_conversation.assert_not_called()
        done_event = [e for e in events if e.type == "done"][0]
        assert done_event.conversation_id == existing_conv_id
