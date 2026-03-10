"""Integration smoke tests for dashboard and analytics endpoints."""


async def test_dashboard_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
    assert r.status_code == 200


async def test_sentiment_trends_returns_200(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/sentiment-trends?days=7"
    )
    assert r.status_code == 200
    assert "data" in r.json()


async def test_gap_events_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/gap-events")
    assert r.status_code == 200


async def test_sentiment_by_segment_returns_200(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/sentiment-by-segment?days=7"
    )
    assert r.status_code == 200
