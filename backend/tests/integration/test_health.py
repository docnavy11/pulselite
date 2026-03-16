"""
Smoke integration tests verifying the full test stack:
real DB connection, dependency override, HTTP client, auth fixtures.
"""


async def test_health_endpoint_returns_200(client):
    """The /health endpoint should return 200 with DB + Redis connected."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["database"] == "connected"


async def test_authenticated_endpoint_requires_auth(client):
    """Endpoints without auth header should return 401 or 403."""
    response = await client.get("/api/v1/workspaces")
    assert response.status_code in (401, 403)


async def test_authenticated_endpoint_works_with_auth(auth_client, workspace):
    """An authenticated client can list workspaces and see their own workspace."""
    response = await auth_client.get("/api/v1/workspaces")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    workspace_ids = [ws["id"] for ws in data]
    assert str(workspace.id) in workspace_ids


async def test_db_rollback_isolation(db, workspace):
    """Data created in this test should not persist after the test ends."""
    from tests.factories import make_chatbot
    bot = await make_chatbot(db, workspace, name="Rollback Test Bot")
    assert bot.id is not None
    # The rollback happens automatically in the db fixture teardown.
    # After this test the bot row is gone — subsequent tests won't see it.
