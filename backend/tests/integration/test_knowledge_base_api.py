"""Integration tests for /workspaces/{workspace_id}/knowledge-bases CRUD."""
import uuid
from tests.factories import make_chatbot, make_knowledge_base


async def test_list_knowledge_bases_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_knowledge_base_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases",
        json={"name": "My KB", "chatbot_id": str(bot.id)},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "My KB"
    assert "id" in data


async def test_create_knowledge_base_appears_in_list(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases",
        json={"name": "Listed KB", "chatbot_id": str(bot.id)},
    )
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases")
    names = [kb["name"] for kb in r.json()]
    assert "Listed KB" in names


async def test_get_knowledge_base_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    kb = await make_knowledge_base(db, workspace, bot, name="Fetch KB")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb.id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Fetch KB"


async def test_get_nonexistent_kb_returns_404(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_delete_knowledge_base_returns_204(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    kb = await make_knowledge_base(db, workspace, bot, name="Delete KB")
    r = await auth_client.delete(f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb.id}")
    assert r.status_code == 204


async def test_delete_kb_then_get_returns_404(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    kb = await make_knowledge_base(db, workspace, bot, name="Gone KB")
    await auth_client.delete(f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb.id}")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb.id}")
    assert r.status_code == 404


async def test_kb_response_has_required_fields(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases",
        json={"name": "Field KB", "chatbot_id": str(bot.id)},
    )
    data = r.json()
    for field in ("id", "name", "workspace_id", "chatbot_id", "kb_type", "created_at"):
        assert field in data, f"Missing field: {field}"


async def test_list_kbs_scoped_to_chatbot(db, auth_client, workspace):
    bot_a = await make_chatbot(db, workspace, name="Bot A")
    bot_b = await make_chatbot(db, workspace, name="Bot B")
    kb_a = await make_knowledge_base(db, workspace, bot_a, name="KB A")
    await make_knowledge_base(db, workspace, bot_b, name="KB B")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases?chatbot_id={bot_a.id}"
    )
    assert r.status_code == 200
    ids = [kb["id"] for kb in r.json()]
    assert str(kb_a.id) in ids


async def test_list_kbs_chatbot_filter_excludes_other_chatbot(db, auth_client, workspace):
    bot_a = await make_chatbot(db, workspace, name="Bot A")
    bot_b = await make_chatbot(db, workspace, name="Bot B")
    await make_knowledge_base(db, workspace, bot_a, name="KB A")
    kb_b = await make_knowledge_base(db, workspace, bot_b, name="KB B")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases?chatbot_id={bot_a.id}"
    )
    assert r.status_code == 200
    ids = [kb["id"] for kb in r.json()]
    assert str(kb_b.id) not in ids


async def test_create_kb_default_type_is_general(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases",
        json={"name": "Default Type KB", "chatbot_id": str(bot.id)},
    )
    assert r.status_code == 200
    assert r.json()["kb_type"] == "general"
