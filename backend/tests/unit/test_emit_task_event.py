import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_emit_task_event_started():
    """emit_task_event emits task:started with correct payload."""
    mock_mgr = AsyncMock()
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_task_event

        await emit_task_event(
            workspace_id="ws-abc",
            event_type="started",
            task_name="analyze_conversation",
            task_id="task-123",
            detail="Processing conversation",
        )

        mock_mgr.emit.assert_awaited_once_with(
            "task:started",
            {
                "task_name": "analyze_conversation",
                "task_id": "task-123",
                "detail": "Processing conversation",
                "current": None,
                "total": None,
                "error": None,
            },
            room="ws-abc",
        )


@pytest.mark.asyncio
async def test_emit_task_event_completed_with_error():
    """emit_task_event emits task:completed with error field."""
    mock_mgr = AsyncMock()
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_task_event

        await emit_task_event(
            workspace_id="ws-abc",
            event_type="completed",
            task_name="export_data",
            task_id="task-456",
            error="Workspace not found",
        )

        mock_mgr.emit.assert_awaited_once_with(
            "task:completed",
            {
                "task_name": "export_data",
                "task_id": "task-456",
                "detail": None,
                "current": None,
                "total": None,
                "error": "Workspace not found",
            },
            room="ws-abc",
        )


@pytest.mark.asyncio
async def test_emit_task_event_progress():
    """emit_task_event emits task:progress with current/total."""
    mock_mgr = AsyncMock()
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_task_event

        await emit_task_event(
            workspace_id="ws-abc",
            event_type="progress",
            task_name="cluster_gaps",
            task_id="task-789",
            current=3,
            total=10,
        )

        mock_mgr.emit.assert_awaited_once_with(
            "task:progress",
            {
                "task_name": "cluster_gaps",
                "task_id": "task-789",
                "detail": None,
                "current": 3,
                "total": 10,
                "error": None,
            },
            room="ws-abc",
        )


@pytest.mark.asyncio
async def test_emit_task_event_uuid_workspace_id():
    """emit_task_event converts UUID workspace_id to string."""
    import uuid

    mock_mgr = AsyncMock()
    ws_uuid = uuid.UUID("350863e7-3dc8-430e-bc23-fd41d4499d7b")
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_task_event

        await emit_task_event(
            workspace_id=ws_uuid,
            event_type="started",
            task_name="export_data",
            task_id="task-1",
        )

        mock_mgr.emit.assert_awaited_once()
        call_args = mock_mgr.emit.call_args
        assert call_args[1]["room"] == "350863e7-3dc8-430e-bc23-fd41d4499d7b"
