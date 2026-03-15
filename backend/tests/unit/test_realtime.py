import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_emit_to_workspace_publishes_event():
    """emit_to_workspace calls mgr.emit with correct room and event."""
    mock_mgr = AsyncMock()
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_to_workspace

        await emit_to_workspace("ws-123", "crawl:progress", {"pages_queued": 5})

        mock_mgr.emit.assert_awaited_once_with(
            "crawl:progress",
            {"pages_queued": 5},
            room="ws-123",
        )


@pytest.mark.asyncio
async def test_emit_to_workspace_noop_when_no_manager():
    """emit_to_workspace is a no-op if manager creation fails."""
    with patch("app.services.realtime._create_manager", return_value=None):
        from app.services.realtime import emit_to_workspace
        # Should not raise
        await emit_to_workspace("ws-123", "test:event", {})
