"""Tests for the admin bootstrap service."""
from unittest.mock import patch, AsyncMock

from sqlalchemy import select, func

from app.models.organizational import Agent, Workspace, WorkspaceMembership
from app.services.bootstrap import bootstrap_admin


async def test_bootstrap_skips_when_no_env_vars():
    """Bootstrap should do nothing when ADMIN_EMAIL/PASSWORD are empty."""
    with patch("app.services.bootstrap.settings") as mock_settings:
        mock_settings.ADMIN_EMAIL = ""
        mock_settings.ADMIN_PASSWORD = ""

        # Should return without touching DB
        await bootstrap_admin()


async def test_bootstrap_skips_when_only_email_set():
    """Bootstrap should do nothing when ADMIN_PASSWORD is missing."""
    with patch("app.services.bootstrap.settings") as mock_settings:
        mock_settings.ADMIN_EMAIL = "admin@test.com"
        mock_settings.ADMIN_PASSWORD = ""

        await bootstrap_admin()
