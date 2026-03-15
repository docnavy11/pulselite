import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_emit_to_workspace_uses_sio_in_api_process():
    """When _get_sio() returns a server instance, emit directly via Socket.IO."""
    from app.services.realtime import emit_to_workspace

    mock_sio = AsyncMock()
    with patch("app.services.realtime._get_sio", return_value=mock_sio):
        await emit_to_workspace("ws-123", "test:event", {"key": "value"})

    mock_sio.emit.assert_awaited_once_with("test:event", {"key": "value"}, room="ws-123")


@pytest.mark.asyncio
async def test_emit_to_workspace_uses_http_in_worker():
    """When _get_sio() returns None (worker), emit via HTTP endpoint."""
    from app.services.realtime import emit_to_workspace

    with patch("app.services.realtime._get_sio", return_value=None), \
         patch("app.services.realtime._emit_via_http", new_callable=AsyncMock) as mock_http:
        await emit_to_workspace("ws-123", "test:event", {"key": "value"})

    mock_http.assert_awaited_once_with("test:event", {"key": "value"}, "ws-123")


@pytest.mark.asyncio
async def test_emit_to_workspace_swallows_exceptions():
    """emit_to_workspace logs but does not raise on failure."""
    from app.services.realtime import emit_to_workspace

    with patch("app.services.realtime._get_sio", side_effect=Exception("connection lost")):
        # Should not raise
        await emit_to_workspace("ws-123", "test:event", {"data": 1})
