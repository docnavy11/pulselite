"""Integration tests for /workspaces/{workspace_id}/conversations."""
import uuid
from tests.factories import make_chatbot, make_conversation, make_message


async def test_list_conversations_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/conversations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_conversations_status_filter(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv_open = await make_conversation(db, workspace, bot, status="open")
    conv_resolved = await make_conversation(db, workspace, bot, status="resolved")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations?status=open"
    )
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert str(conv_open.id) in ids
    assert str(conv_resolved.id) not in ids


async def test_list_conversations_chatbot_filter(db, auth_client, workspace):
    bot_a = await make_chatbot(db, workspace, name="A")
    bot_b = await make_chatbot(db, workspace, name="B")
    conv_a = await make_conversation(db, workspace, bot_a)
    conv_b = await make_conversation(db, workspace, bot_b)
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations?chatbot_id={bot_a.id}"
    )
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert str(conv_a.id) in ids
    assert str(conv_b.id) not in ids


async def test_get_conversation_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot)
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/{conv.id}"
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(conv.id)


async def test_get_nonexistent_conversation_returns_404(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/{uuid.uuid4()}"
    )
    assert r.status_code == 404


async def test_get_conversation_messages(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot)
    await make_message(db, conv, workspace, content="Hello")
    await make_message(db, conv, workspace, content="World", author_type="bot")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/{conv.id}/messages"
    )
    assert r.status_code == 200
    messages = r.json()
    assert len(messages) == 2
    assert messages[0]["content"] == "Hello"


async def test_export_conversations_returns_csv(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    await make_conversation(db, workspace, bot)
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/export"
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


async def test_conversations_response_has_required_fields(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    await make_conversation(db, workspace, bot)
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/conversations")
    convs = r.json()
    if convs:
        for field in ("id", "workspace_id", "status", "created_at"):
            assert field in convs[0], f"Missing field: {field}"
