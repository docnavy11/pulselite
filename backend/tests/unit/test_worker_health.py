"""Tests for worker health endpoint."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from app.models.task_log import BackgroundTaskLog


@pytest.mark.asyncio
async def test_worker_health_empty(auth_client, workspace):
    """Returns zero stats when no task logs exist."""
    resp = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/workers/health?window=24h"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["queue"]["pending"] == 0
    assert data["queue"]["running"] == 0
    assert data["reliability"]["total"] == 0
    assert data["reliability"]["failure_rate_pct"] == 0.0
    assert data["performance"]["by_task"] == []
    assert data["timeseries"] == []


@pytest.mark.asyncio
async def test_worker_health_with_data(auth_client, workspace, db):
    """Returns correct aggregated stats."""
    now = datetime.now(timezone.utc)

    # Create some completed task logs
    for i in range(5):
        log = BackgroundTaskLog(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            task_name="ingest_document",
            task_id=f"task-{i}",
            status="completed",
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=30),
            duration_ms=3000 + (i * 100),
        )
        db.add(log)

    # Add a failed task
    failed = BackgroundTaskLog(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        task_name="crawl_website",
        task_id="task-fail",
        status="failed",
        started_at=now - timedelta(hours=1),
        completed_at=now - timedelta(minutes=50),
        duration_ms=500,
        error="Connection timeout",
    )
    db.add(failed)

    # Add a running task (should appear in queue)
    running = BackgroundTaskLog(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        task_name="analyze_conversation",
        task_id="task-running",
        status="running",
        started_at=now - timedelta(minutes=2),
    )
    db.add(running)
    await db.flush()

    resp = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/workers/health?window=24h"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["queue"]["running"] == 1
    # total = completed (5) + failed (1) = 6; running task excluded from reliability
    assert data["reliability"]["total"] == 6
    assert data["reliability"]["succeeded"] == 5
    assert data["reliability"]["failed"] == 1
    assert len(data["performance"]["by_task"]) >= 2

    # Check ingest_document performance
    ingest = next(t for t in data["performance"]["by_task"] if t["task_name"] == "ingest_document")
    assert ingest["count"] == 5
    assert ingest["success_rate_pct"] == 100.0
    assert ingest["avg_duration_ms"] is not None


@pytest.mark.asyncio
async def test_worker_health_requires_admin(auth_client, workspace):
    """Endpoint exists and returns 200 for admin user."""
    resp = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/workers/health"
    )
    assert resp.status_code == 200
