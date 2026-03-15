import uuid
import pytest
from app.services.chatbot_service import create_chatbot, update_chatbot


@pytest.mark.asyncio
async def test_update_chatbot_can_clear_nullable_field(db, workspace):
    """Explicitly setting fallback_message=None should clear it."""
    chatbot = await create_chatbot(db, workspace.id, name="test", fallback_message="old msg")
    await db.flush()

    updated = await update_chatbot(db, workspace.id, chatbot.id, fallback_message=None)
    assert updated.fallback_message is None, "Should be able to clear nullable fields"


@pytest.mark.asyncio
async def test_update_chatbot_can_clear_system_prompt(db, workspace):
    chatbot = await create_chatbot(db, workspace.id, name="test", system_prompt="old prompt")
    await db.flush()

    updated = await update_chatbot(db, workspace.id, chatbot.id, system_prompt=None)
    assert updated.system_prompt is None
