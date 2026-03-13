import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_emit_to_workspace_publishes_event():
    """emit_to_workspace calls mgr.emit with correct room and event."""
    with patch("app.services.realtime._mgr") as mock_mgr:
        mock_mgr.emit = AsyncMock()
        from app.services.realtime import emit_to_workspace

        await emit_to_workspace("ws-123", "crawl:progress", {"pages_queued": 5})

        mock_mgr.emit.assert_awaited_once_with(
            "crawl:progress",
            {"pages_queued": 5},
            room="ws-123",
        )


@pytest.mark.asyncio
async def test_emit_to_workspace_noop_when_no_manager():
    """emit_to_workspace is a no-op if manager is not initialized."""
    with patch("app.services.realtime._mgr", None):
        with patch("app.services.realtime._get_manager", return_value=None):
            from app.services.realtime import emit_to_workspace
            # Should not raise
            await emit_to_workspace("ws-123", "test:event", {})
