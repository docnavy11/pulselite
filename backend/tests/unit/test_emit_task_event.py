import uuid

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_emit_task_event_started():
    """emit_task_event emits task:started with correct payload."""
    from app.services.realtime import emit_task_event

    with patch("app.services.realtime.emit_to_workspace", new_callable=AsyncMock) as mock_emit, \
         patch("app.services.realtime.write_task_state", new_callable=AsyncMock), \
         patch("app.services.realtime._log_task_event", new_callable=AsyncMock):
        await emit_task_event(
            workspace_id="ws-abc",
            event_type="started",
            task_name="analyze_conversation",
            task_id="task-123",
            detail="Processing conversation",
        )

    mock_emit.assert_awaited_once_with(
        "ws-abc",
        "task:started",
        {
            "task_name": "analyze_conversation",
            "task_id": "task-123",
            "detail": "Processing conversation",
            "current": None,
            "total": None,
            "error": None,
        },
    )


@pytest.mark.asyncio
async def test_emit_task_event_completed_with_error():
    """emit_task_event emits task:completed with error field."""
    from app.services.realtime import emit_task_event

    with patch("app.services.realtime.emit_to_workspace", new_callable=AsyncMock) as mock_emit, \
         patch("app.services.realtime.clear_task_state", new_callable=AsyncMock), \
         patch("app.services.realtime._log_task_event", new_callable=AsyncMock):
        await emit_task_event(
            workspace_id="ws-abc",
            event_type="completed",
            task_name="export_data",
            task_id="task-456",
            error="Workspace not found",
        )

    mock_emit.assert_awaited_once_with(
        "ws-abc",
        "task:completed",
        {
            "task_name": "export_data",
            "task_id": "task-456",
            "detail": None,
            "current": None,
            "total": None,
            "error": "Workspace not found",
        },
    )


@pytest.mark.asyncio
async def test_emit_task_event_progress():
    """emit_task_event emits task:progress with current/total."""
    from app.services.realtime import emit_task_event

    with patch("app.services.realtime.emit_to_workspace", new_callable=AsyncMock) as mock_emit, \
         patch("app.services.realtime.write_task_state", new_callable=AsyncMock), \
         patch("app.services.realtime._log_task_event", new_callable=AsyncMock):
        await emit_task_event(
            workspace_id="ws-abc",
            event_type="progress",
            task_name="cluster_gaps",
            task_id="task-789",
            current=3,
            total=10,
        )

    mock_emit.assert_awaited_once_with(
        "ws-abc",
        "task:progress",
        {
            "task_name": "cluster_gaps",
            "task_id": "task-789",
            "detail": None,
            "current": 3,
            "total": 10,
            "error": None,
        },
    )


@pytest.mark.asyncio
async def test_emit_task_event_uuid_workspace_id():
    """emit_task_event converts UUID workspace_id to string."""
    from app.services.realtime import emit_task_event

    ws_uuid = uuid.UUID("350863e7-3dc8-430e-bc23-fd41d4499d7b")
    with patch("app.services.realtime.emit_to_workspace", new_callable=AsyncMock) as mock_emit, \
         patch("app.services.realtime.write_task_state", new_callable=AsyncMock), \
         patch("app.services.realtime._log_task_event", new_callable=AsyncMock):
        await emit_task_event(
            workspace_id=ws_uuid,
            event_type="started",
            task_name="export_data",
            task_id="task-1",
        )

    mock_emit.assert_awaited_once()
    call_args = mock_emit.call_args
    assert call_args[0][0] == "350863e7-3dc8-430e-bc23-fd41d4499d7b"
