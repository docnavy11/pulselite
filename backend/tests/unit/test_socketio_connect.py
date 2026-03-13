# backend/tests/unit/test_socketio_connect.py
import pytest
from unittest.mock import AsyncMock, patch


class TestSocketIOConnect:
    @pytest.mark.asyncio
    async def test_connect_rejects_missing_token(self):
        """Connection without token should be refused."""
        from app.main import _sio_connect

        with pytest.raises(Exception):
            await _sio_connect("sid-1", {}, None)

    @pytest.mark.asyncio
    async def test_connect_rejects_invalid_token(self):
        """Connection with invalid token should be refused."""
        from app.main import _sio_connect

        with patch("app.main.decode_token", return_value=None):
            with pytest.raises(Exception):
                await _sio_connect("sid-1", {}, {"token": "bad-token"})

    @pytest.mark.asyncio
    async def test_connect_accepts_valid_token(self):
        """Connection with valid token should succeed."""
        from app.main import _sio_connect

        with patch("app.main.decode_token", return_value={"sub": "user-123", "type": "access"}):
            with patch("app.main.sio") as mock_sio:
                mock_sio.save_session = AsyncMock()
                # Should not raise
                await _sio_connect("sid-1", {}, {"token": "valid-token"})
                mock_sio.save_session.assert_awaited_once()
