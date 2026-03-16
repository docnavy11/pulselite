"""Integration tests for /workspaces/{workspace_id}/chatbots CRUD."""
import uuid
from unittest.mock import patch

from sqlalchemy import select

from tests.factories import make_chatbot, make_knowledge_base, make_crawl_job, make_document


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


# ── AI config validation on chatbot creation ──────────────────────────────


async def test_create_chatbot_fails_without_ai_key(db, auth_client, workspace):
    """When no AI key is configured (neither workspace nor env), return 400."""
    with patch("app.api.v1.chatbots.app_settings") as mock_settings:
        mock_settings.AI_API_KEY = ""
        mock_settings.DEFAULT_CHATBOT_MODEL = ""
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/chatbots",
            json={"name": "Should Fail"},
        )
    assert r.status_code == 400
    assert "No AI provider configured" in r.json()["detail"]


async def test_create_chatbot_succeeds_with_env_ai_key(auth_client, workspace):
    """When AI_API_KEY is set in env (via conftest), chatbot creation works."""
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Env Key Bot", "llm_model": "gpt-4o-mini"},
    )
    assert r.status_code == 200


async def test_create_chatbot_succeeds_with_workspace_key(db, auth_client, workspace):
    """When workspace has openrouter_api_key set, chatbot creation works even without env key."""
    from app.models.organizational import Workspace
    from app.services.encryption import encrypt_api_key

    result = await db.execute(select(Workspace).where(Workspace.id == workspace.id))
    ws = result.scalar_one()
    ws.openrouter_api_key = encrypt_api_key("sk-or-v1-test")
    await db.flush()

    with patch("app.api.v1.chatbots.app_settings") as mock_settings:
        mock_settings.AI_API_KEY = ""
        mock_settings.DEFAULT_CHATBOT_MODEL = ""
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/chatbots",
            json={"name": "Workspace Key Bot", "llm_model": "gpt-4o-mini"},
        )
    assert r.status_code == 200


async def test_create_chatbot_fails_with_disallowed_model(db, auth_client, workspace):
    """When workspace has allowed_models, creating a chatbot with an unlisted model returns 400."""
    from app.models.organizational import Workspace

    result = await db.execute(select(Workspace).where(Workspace.id == workspace.id))
    ws = result.scalar_one()
    ws.allowed_models = ["model-a", "model-b"]
    await db.flush()

    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Bad Model Bot", "llm_model": "model-c"},
    )
    assert r.status_code == 400
    assert "not in the workspace's allowed models" in r.json()["detail"]


async def test_create_chatbot_succeeds_with_allowed_model(db, auth_client, workspace):
    """When workspace has allowed_models, creating with a listed model succeeds."""
    from app.models.organizational import Workspace

    result = await db.execute(select(Workspace).where(Workspace.id == workspace.id))
    ws = result.scalar_one()
    ws.allowed_models = ["model-a", "model-b"]
    await db.flush()

    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Good Model Bot", "llm_model": "model-a"},
    )
    assert r.status_code == 200
    assert r.json()["llm_model"] == "model-a"


async def test_create_chatbot_no_model_restriction_when_allowed_models_empty(auth_client, workspace):
    """When allowed_models is empty (default), any model is allowed."""
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Any Model Bot", "llm_model": "some-random-model"},
    )
    assert r.status_code == 200


# ── Cascading delete with crawl jobs ──────────────────────────────────────


async def test_delete_chatbot_with_crawl_jobs(db, auth_client, workspace):
    """Deleting a chatbot that has KBs, documents, and crawl jobs should not crash."""
    bot = await make_chatbot(db, workspace, name="Bot With Crawl")
    kb = await make_knowledge_base(db, workspace, bot)
    await make_document(db, workspace, kb, title="Doc 1")
    job = await make_crawl_job(db, workspace, kb)
    # Link crawl job to chatbot
    bot.active_crawl_job_id = job.id
    await db.flush()

    r = await auth_client.delete(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
    assert r.status_code == 204
