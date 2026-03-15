import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_message(author_type, content, message_type="incoming"):
    msg = MagicMock()
    msg.author_type = author_type
    msg.content = content
    msg.message_type = message_type
    return msg


class TestGetConversationHistory:
    @pytest.mark.asyncio
    async def test_returns_role_mapped_messages(self):
        from app.services.rag.memory import get_conversation_history

        messages = [
            _make_message("bot", "Click the login button.", "outgoing"),
            _make_message("contact", "How do I login?", "incoming"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = messages

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        history = await get_conversation_history(db, uuid.uuid4())
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "How do I login?"}
        assert history[1] == {"role": "assistant", "content": "Click the login button."}

    @pytest.mark.asyncio
    async def test_skips_empty_content(self):
        from app.services.rag.memory import get_conversation_history

        messages = [
            _make_message("contact", None, "incoming"),
            _make_message("bot", "Response", "outgoing"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = messages

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        history = await get_conversation_history(db, uuid.uuid4())
        assert len(history) == 1
        assert history[0]["content"] == "Response"

    @pytest.mark.asyncio
    async def test_agent_maps_to_assistant(self):
        from app.services.rag.memory import get_conversation_history

        messages = [_make_message("agent", "I'll help you.")]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = messages

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        history = await get_conversation_history(db, uuid.uuid4())
        assert history[0]["role"] == "assistant"
