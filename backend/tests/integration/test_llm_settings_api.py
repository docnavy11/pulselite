"""Integration tests for /workspaces/{workspace_id}/llm-settings endpoints."""
from unittest.mock import patch


async def test_get_llm_settings_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/llm-settings")
    assert r.status_code == 200
    data = r.json()
    assert "allowed_models" in data
    assert "internal_model" in data
    assert "default_chatbot_model" in data
    assert data["allowed_models"] == []
    assert data["internal_model"] is None
    assert data["default_chatbot_model"] is None


async def test_put_allowed_models(auth_client, workspace):
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"allowed_models": ["model-a", "model-b"]},
    )
    assert r.status_code == 200
    assert r.json()["allowed_models"] == ["model-a", "model-b"]


async def test_put_internal_model(auth_client, workspace):
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"internal_model": "anthropic/claude-sonnet"},
    )
    assert r.status_code == 200
    assert r.json()["internal_model"] == "anthropic/claude-sonnet"


async def test_put_default_chatbot_model(auth_client, workspace):
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"default_chatbot_model": "openai/gpt-4o"},
    )
    assert r.status_code == 200
    assert r.json()["default_chatbot_model"] == "openai/gpt-4o"


async def test_clear_default_chatbot_model(auth_client, workspace):
    # Set it first
    await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"default_chatbot_model": "openai/gpt-4o"},
    )
    # Clear it
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"default_chatbot_model": ""},
    )
    assert r.status_code == 200
    assert r.json()["default_chatbot_model"] is None


async def test_put_internal_model_does_not_wipe_allowed_models(auth_client, workspace):
    """Saving internal_model alone should not overwrite allowed_models."""
    await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"allowed_models": ["model-a", "model-b"]},
    )
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"internal_model": "anthropic/claude-sonnet"},
    )
    assert r.status_code == 200
    assert r.json()["allowed_models"] == ["model-a", "model-b"]


async def test_put_default_chatbot_model_does_not_wipe_allowed_models(auth_client, workspace):
    """Saving default_chatbot_model alone should not overwrite allowed_models."""
    await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"allowed_models": ["model-x"]},
    )
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"default_chatbot_model": "model-x"},
    )
    assert r.status_code == 200
    assert r.json()["allowed_models"] == ["model-x"]
    assert r.json()["default_chatbot_model"] == "model-x"


async def test_allowed_models_max_100(auth_client, workspace):
    models = [f"model-{i}" for i in range(101)]
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/llm-settings",
        json={"allowed_models": models},
    )
    assert r.status_code == 400


# ── Models endpoint — base URL validation ─────────────────────────────────


async def test_models_endpoint_returns_400_when_no_api_key(db, auth_client, workspace):
    """When no API key is configured at all, /models returns 400."""
    with patch("app.api.v1.workspaces.app_settings") as mock_settings:
        mock_settings.AI_API_KEY = ""
        mock_settings.AI_BASE_URL = ""
        r = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/llm-settings/models",
        )
    assert r.status_code == 400
    assert "No API key configured" in r.json()["detail"]


async def test_models_endpoint_returns_400_when_no_base_url(db, auth_client, workspace):
    """When API key is set but no base URL, /models returns 400 (not a 500 crash)."""
    with patch("app.api.v1.workspaces.app_settings") as mock_settings:
        mock_settings.AI_API_KEY = "sk-test-key"
        mock_settings.AI_BASE_URL = ""
        r = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/llm-settings/models",
        )
    assert r.status_code == 400
    assert "No AI base URL configured" in r.json()["detail"]


async def test_get_llm_settings_shows_env_fields(auth_client, workspace):
    """LLM settings response includes env-level fields for UI display."""
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/llm-settings")
    assert r.status_code == 200
    data = r.json()
    # env_api_key_set should reflect the AI_API_KEY set in conftest
    assert "env_api_key_set" in data
    assert "env_base_url" in data
    assert "effective_api_key_set" in data
    assert "effective_base_url" in data


async def test_get_llm_settings_effective_key_true_with_env_key(auth_client, workspace):
    """effective_api_key_set is True when AI_API_KEY is set in env."""
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/llm-settings")
    assert r.status_code == 200
    # AI_API_KEY is set to "test-ai-key" in conftest
    assert r.json()["effective_api_key_set"] is True


async def test_create_chatbot_uses_workspace_default_model(db, auth_client, workspace):
    """When workspace has a default_chatbot_model, new chatbots should use it."""
    from app.models.organizational import Workspace
    from sqlalchemy import select

    result = await db.execute(select(Workspace).where(Workspace.id == workspace.id))
    ws = result.scalar_one()
    ws.default_chatbot_model = "openai/gpt-4o"
    await db.flush()

    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Default Model Bot"},
    )
    assert r.status_code == 200
    assert r.json()["llm_model"] == "openai/gpt-4o"


async def test_create_chatbot_explicit_model_overrides_default(db, auth_client, workspace):
    """When an explicit llm_model is provided, it should override the workspace default."""
    from app.models.organizational import Workspace
    from sqlalchemy import select

    result = await db.execute(select(Workspace).where(Workspace.id == workspace.id))
    ws = result.scalar_one()
    ws.default_chatbot_model = "openai/gpt-4o"
    await db.flush()

    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Explicit Model Bot", "llm_model": "anthropic/claude-sonnet"},
    )
    assert r.status_code == 200
    assert r.json()["llm_model"] == "anthropic/claude-sonnet"


async def test_create_chatbot_no_default_uses_schema_default(auth_client, workspace):
    """When no workspace default is set, chatbot uses the schema default model."""
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Schema Default Bot"},
    )
    assert r.status_code == 200
    assert r.json()["llm_model"] == "claude-haiku-4-5-20251001"


async def test_create_chatbot_uses_env_default_model(auth_client, workspace):
    """When workspace has no default but env DEFAULT_CHATBOT_MODEL is set, use it."""
    from unittest.mock import patch
    with patch("app.api.v1.chatbots.app_settings") as mock_settings:
        mock_settings.DEFAULT_CHATBOT_MODEL = "google/gemini-pro"
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/chatbots",
            json={"name": "Env Default Bot"},
        )
        assert r.status_code == 200
        assert r.json()["llm_model"] == "google/gemini-pro"


async def test_workspace_default_overrides_env_default(db, auth_client, workspace):
    """Workspace default_chatbot_model should take precedence over env var."""
    from unittest.mock import patch
    from app.models.organizational import Workspace
    from sqlalchemy import select

    result = await db.execute(select(Workspace).where(Workspace.id == workspace.id))
    ws = result.scalar_one()
    ws.default_chatbot_model = "anthropic/claude-sonnet"
    await db.flush()

    with patch("app.api.v1.chatbots.app_settings") as mock_settings:
        mock_settings.DEFAULT_CHATBOT_MODEL = "google/gemini-pro"
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/chatbots",
            json={"name": "Override Bot"},
        )
        assert r.status_code == 200
        assert r.json()["llm_model"] == "anthropic/claude-sonnet"
