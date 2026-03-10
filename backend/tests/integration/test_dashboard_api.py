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


async def test_topics_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/topics")
    assert r.status_code == 200


async def test_leads_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/leads")
    assert r.status_code == 200


async def test_feature_requests_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/feature-requests")
    assert r.status_code == 200


async def test_resolution_stats_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/resolution-stats")
    assert r.status_code == 200


async def test_gap_events_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/gap-events")
    assert r.status_code == 200


async def test_chats_by_country_returns_200(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/analytics/chats-by-country"
    )
    assert r.status_code == 200


async def test_sentiment_by_segment_returns_200(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/sentiment-by-segment?days=7"
    )
    assert r.status_code == 200
