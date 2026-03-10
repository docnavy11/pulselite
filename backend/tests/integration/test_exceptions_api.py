"""Integration tests for /workspaces/{workspace_id}/exceptions."""
import uuid
from tests.factories import make_chatbot, make_conversation, make_message


async def test_list_exceptions_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


async def test_list_exceptions_returns_list_and_total(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    data = r.json()
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)


async def test_list_exceptions_only_includes_escalated(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    # autonomous_resolved=True + no escalation_reason → should NOT appear
    conv_resolved = await make_conversation(db, workspace, bot, autonomous_resolved=True)
    # status="closed" → should NOT appear (wrong status)
    conv_closed = await make_conversation(
        db, workspace, bot, status="closed", autonomous_resolved=False
    )
    # escalation_reason set → SHOULD appear
    conv_exc = await make_conversation(
        db, workspace, bot, escalation_reason="low_confidence", autonomous_resolved=False
    )
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert str(conv_exc.id) in ids
    assert str(conv_resolved.id) not in ids
    assert str(conv_closed.id) not in ids


async def test_list_exceptions_includes_unresolved_open(db, auth_client, workspace):
    """open + autonomous_resolved=False (default) qualifies as an exception."""
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, autonomous_resolved=False)
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert str(conv.id) in ids


async def test_list_exceptions_item_has_required_fields(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    item = items[0]
    for field in ("id", "workspace_id", "status", "escalation_reason", "created_at"):
        assert field in item, f"Missing field in exception item: {field}"


async def test_list_exceptions_filter_by_escalation_reason(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    await make_conversation(db, workspace, bot, escalation_reason="sentiment_negative")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions",
        params={"escalation_reason": "low_confidence"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["escalation_reason"] == "low_confidence" for i in items)


async def test_list_exceptions_filter_by_chatbot_id(db, auth_client, workspace):
    bot_a = await make_chatbot(db, workspace)
    bot_b = await make_chatbot(db, workspace)
    conv_a = await make_conversation(db, workspace, bot_a, escalation_reason="low_confidence")
    await make_conversation(db, workspace, bot_b, escalation_reason="low_confidence")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions",
        params={"chatbot_id": str(bot_a.id)},
    )
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert str(conv_a.id) in ids
    assert all(i["chatbot_id"] == str(bot_a.id) for i in r.json()["items"])


async def test_get_exception_detail_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    await make_message(db, conv, workspace, content="Help me")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}"
    )
    assert r.status_code == 200
    data = r.json()
    assert "conversation" in data
    assert "messages" in data


async def test_get_exception_detail_conversation_fields(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}"
    )
    assert r.status_code == 200
    convo = r.json()["conversation"]
    assert convo["id"] == str(conv.id)
    assert convo["escalation_reason"] == "low_confidence"


async def test_get_exception_detail_messages_list(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    await make_message(db, conv, workspace, content="First message")
    await make_message(db, conv, workspace, content="Second message", author_type="bot")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}"
    )
    assert r.status_code == 200
    messages = r.json()["messages"]
    assert len(messages) == 2
    contents = [m["content"] for m in messages]
    assert "First message" in contents
    assert "Second message" in contents


async def test_get_exception_detail_no_messages(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}"
    )
    assert r.status_code == 200
    assert r.json()["messages"] == []


async def test_get_nonexistent_exception_returns_404(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{uuid.uuid4()}"
    )
    assert r.status_code == 404


async def test_resolve_exception_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}/resolve"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["conversation_id"] == str(conv.id)


async def test_resolve_nonexistent_exception_returns_404(auth_client, workspace):
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{uuid.uuid4()}/resolve"
    )
    assert r.status_code == 404


async def test_reply_to_exception_returns_201(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}/reply",
        json={"content": "Hi, I can help you with that.", "resolve": False},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "ok"
    assert "message_id" in data


async def test_reply_with_resolve_true(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}/reply",
        json={"content": "Resolved your issue!", "resolve": True},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["resolved"] is True


async def test_reply_without_resolve_flag_defaults_to_false(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}/reply",
        json={"content": "Just a reply, not resolving."},
    )
    assert r.status_code == 201
    assert r.json()["resolved"] is False


async def test_reply_to_nonexistent_exception_returns_404(auth_client, workspace):
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{uuid.uuid4()}/reply",
        json={"content": "Hello?", "resolve": False},
    )
    assert r.status_code == 404


async def test_resolved_exception_no_longer_appears_in_list(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot, escalation_reason="low_confidence")
    # Verify it initially appears
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    ids_before = [i["id"] for i in r.json()["items"]]
    assert str(conv.id) in ids_before
    # Resolve it
    await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}/resolve"
    )
    # Should no longer appear (status is now "resolved", not "open")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    ids_after = [i["id"] for i in r.json()["items"]]
    assert str(conv.id) not in ids_after
