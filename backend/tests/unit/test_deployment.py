"""Tests for deployment mode service."""
from unittest.mock import patch

from fastapi import HTTPException
import pytest

from app.services.deployment import is_cloud, is_self_hosted, require_cloud, cloud_or_200


def test_is_cloud_returns_true_when_cloud_mode_enabled():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = True
        assert is_cloud() is True


def test_is_cloud_returns_false_when_cloud_mode_disabled():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        assert is_cloud() is False


def test_is_self_hosted_returns_true_when_cloud_mode_disabled():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        assert is_self_hosted() is True


def test_is_self_hosted_returns_false_when_cloud_mode_enabled():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = True
        assert is_self_hosted() is False


@pytest.mark.asyncio
async def test_require_cloud_raises_404_when_self_hosted():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        with pytest.raises(HTTPException) as exc_info:
            await require_cloud()
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_require_cloud_passes_when_cloud():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = True
        result = await require_cloud()
        assert result is None


@pytest.mark.asyncio
async def test_cloud_or_200_returns_response_when_self_hosted():
    from starlette.responses import Response
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        result = await cloud_or_200()
        assert isinstance(result, Response)
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_cloud_or_200_returns_none_when_cloud():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = True
        result = await cloud_or_200()
        assert result is None
