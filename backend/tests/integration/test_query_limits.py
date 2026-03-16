"""Tests for query limits, pagination caps, and export safeguards."""


async def test_retrieval_logs_rejects_offset_above_10000(auth_client, workspace):
    """Offset above 10K should be rejected to prevent deep pagination table scans."""
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/retrieval-logs?offset=10001"
    )
    assert r.status_code == 422


async def test_gap_events_rejects_offset_above_10000(auth_client, workspace):
    """Offset above 10K should be rejected."""
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/gap-events?offset=10001"
    )
    assert r.status_code == 422


async def test_retrieval_logs_accepts_offset_at_10000(auth_client, workspace):
    """Offset at exactly 10K should be accepted."""
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/retrieval-logs?offset=10000"
    )
    assert r.status_code == 200


async def test_export_conversations_accepts_days_param(auth_client, workspace):
    """Export should accept a days parameter to limit the time window."""
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/export?days=7"
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")


async def test_export_conversations_rejects_days_above_365(auth_client, workspace):
    """Export days above 365 should be rejected."""
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/export?days=400"
    )
    assert r.status_code == 422
