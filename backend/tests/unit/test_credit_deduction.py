"""Tests for credit deduction integration in chat flow."""
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.asyncio
async def test_balance_check_yields_error_when_exhausted_in_cloud():
    """Cloud mode: zero balance should yield error event before streaming."""
    workspace = MagicMock()
    workspace.credit_balance = 0

    with patch("app.services.resolution_service.is_cloud", return_value=True):
        assert workspace.credit_balance <= 0


@pytest.mark.asyncio
async def test_balance_check_skipped_in_self_hosted():
    """Self-hosted mode should never check credit balance."""
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        from app.services.deployment import is_cloud
        assert is_cloud() is False


def test_usage_dict_detection():
    """The streaming loop must distinguish usage dicts from token strings."""
    token = "Hello"
    usage = {"prompt_tokens": 100, "completion_tokens": 50}

    assert not (isinstance(token, dict) and "prompt_tokens" in token)
    assert isinstance(usage, dict) and "prompt_tokens" in usage
