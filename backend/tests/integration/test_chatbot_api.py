"""Integration tests for /workspaces/{workspace_id}/chatbots CRUD."""
import uuid
from tests.factories import make_chatbot


async def test_list_chatbots_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_chatbot_returns_200(auth_client, workspace):
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "My Bot", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "My Bot"
    assert "id" in data


async def test_create_chatbot_appears_in_list(auth_client, workspace):
    await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Listed Bot", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
    )
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots")
    names = [c["name"] for c in r.json()]
    assert "Listed Bot" in names


async def test_get_chatbot_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace, name="Fetch Me")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Fetch Me"


async def test_get_nonexistent_chatbot_returns_404(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_update_chatbot_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace, name="Old Name")
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}",
        json={"name": "New Name"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


async def test_delete_chatbot_returns_204(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace, name="Delete Me")
    r = await auth_client.delete(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
    assert r.status_code == 204


async def test_delete_chatbot_then_get_returns_404(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace, name="Gone Bot")
    await auth_client.delete(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
    assert r.status_code == 404


async def test_chatbot_response_has_required_fields(auth_client, workspace):
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Field Bot", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
    )
    data = r.json()
    for field in ("id", "name", "workspace_id", "llm_provider", "llm_model"):
        assert field in data, f"Missing field: {field}"
