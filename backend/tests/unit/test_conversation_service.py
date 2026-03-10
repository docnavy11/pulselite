"""Unit tests for app.services.conversation_service."""
import pytest
from app.services.conversation_service import (
    create_conversation,
    add_message,
    list_conversations,
    get_messages,
    update_conversation_status,
)
from tests.factories import make_chatbot, make_conversation


@pytest.mark.asyncio
async def test_create_conversation_defaults(db, workspace):
    """create_conversation sets workspace_id, chatbot_id, and defaults status to 'open'."""
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    assert conv.workspace_id == workspace.id
    assert conv.chatbot_id == chatbot.id
    assert conv.status == "open"


@pytest.mark.asyncio
async def test_add_message_user(db, workspace):
    """add_message persists a user message with correct content and author_type."""
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    msg = await add_message(
        db,
        conversation_id=conv.id,
        workspace_id=workspace.id,
        content="Hello!",
        author_type="user",
        message_type="incoming",
    )
    assert msg.content == "Hello!"
    assert msg.author_type == "user"
    assert msg.conversation_id == conv.id


@pytest.mark.asyncio
async def test_add_message_bot_with_confidence(db, workspace):
    """add_message stores the optional confidence_score on a bot message."""
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    msg = await add_message(
        db,
        conversation_id=conv.id,
        workspace_id=workspace.id,
        content="I can help.",
        author_type="bot",
        message_type="outgoing",
        confidence_score=0.92,
    )
    assert msg.confidence_score == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_get_messages_ordered_asc(db, workspace):
    """get_messages returns messages in ascending created_at order."""
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    await add_message(db, conv.id, workspace.id, "First", "user", "incoming")
    await add_message(db, conv.id, workspace.id, "Second", "bot", "outgoing")
    messages = await get_messages(db, conv.id, workspace.id)
    assert len(messages) == 2
    assert messages[0].content == "First"
    assert messages[1].content == "Second"


@pytest.mark.asyncio
async def test_list_conversations_status_filter(db, workspace):
    """list_conversations with status_filter='open' excludes resolved conversations."""
    chatbot = await make_chatbot(db, workspace)
    conv_open = await make_conversation(db, workspace, chatbot, status="open")
    conv_resolved = await make_conversation(db, workspace, chatbot, status="resolved")
    open_list = await list_conversations(db, workspace.id, status_filter="open")
    open_ids = [c.id for c in open_list]
    assert conv_open.id in open_ids
    assert conv_resolved.id not in open_ids


@pytest.mark.asyncio
async def test_list_conversations_chatbot_filter(db, workspace):
    """list_conversations with chatbot_id only returns conversations for that chatbot."""
    bot_a = await make_chatbot(db, workspace, name="Bot A")
    bot_b = await make_chatbot(db, workspace, name="Bot B")
    conv_a = await make_conversation(db, workspace, bot_a)
    conv_b = await make_conversation(db, workspace, bot_b)
    result = await list_conversations(db, workspace.id, chatbot_id=bot_a.id)
    result_ids = [c.id for c in result]
    assert conv_a.id in result_ids
    assert conv_b.id not in result_ids


@pytest.mark.asyncio
async def test_update_conversation_status(db, workspace):
    """update_conversation_status changes status to the requested value."""
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    updated = await update_conversation_status(db, conv.id, "resolved", workspace.id)
    assert updated.status == "resolved"


@pytest.mark.asyncio
async def test_list_conversations_workspace_isolation(db, workspace, second_workspace):
    """list_conversations never leaks conversations across workspace boundaries."""
    bot_a = await make_chatbot(db, workspace)
    bot_b = await make_chatbot(db, second_workspace)
    conv_a = await make_conversation(db, workspace, bot_a)
    conv_b = await make_conversation(db, second_workspace, bot_b)

    result_a = await list_conversations(db, workspace.id)
    result_b = await list_conversations(db, second_workspace.id)
    ids_a = [c.id for c in result_a]
    ids_b = [c.id for c in result_b]

    assert conv_a.id in ids_a
    assert conv_b.id not in ids_a
    assert conv_b.id in ids_b
    assert conv_a.id not in ids_b
