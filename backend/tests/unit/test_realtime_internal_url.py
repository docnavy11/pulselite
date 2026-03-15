import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestEmitViaHttpUrl:
    @pytest.mark.asyncio
    async def test_uses_internal_api_url_from_settings(self):
        """_emit_via_http should use settings.INTERNAL_API_URL, not a hardcoded hostname."""
        from app.services import realtime

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.realtime.settings") as mock_settings, \
             patch("httpx.AsyncClient", return_value=mock_client_instance):
            mock_settings.INTERNAL_API_URL = "http://127.0.0.1:8000"
            mock_settings.SECRET_KEY = "test-secret"

            await realtime._emit_via_http("test:event", {"key": "val"}, "room-1")

        mock_client_instance.post.assert_called_once()
        call_url = mock_client_instance.post.call_args[0][0]
        assert call_url == "http://127.0.0.1:8000/api/internal/emit"

    @pytest.mark.asyncio
    async def test_default_url_uses_backend_hostname(self):
        """Default INTERNAL_API_URL should produce the old http://backend:8000 URL."""
        from app.services import realtime

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.realtime.settings") as mock_settings, \
             patch("httpx.AsyncClient", return_value=mock_client_instance):
            mock_settings.INTERNAL_API_URL = "http://backend:8000"
            mock_settings.SECRET_KEY = "test-secret"

            await realtime._emit_via_http("test:event", {"key": "val"}, "room-1")

        call_url = mock_client_instance.post.call_args[0][0]
        assert call_url == "http://backend:8000/api/internal/emit"
