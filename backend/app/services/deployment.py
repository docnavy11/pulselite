"""Deployment mode helpers — cloud vs self-hosted."""

from fastapi import HTTPException
from starlette.responses import Response

from app.config import settings


def is_cloud() -> bool:
    return settings.CLOUD_MODE


def is_self_hosted() -> bool:
    return not settings.CLOUD_MODE


async def require_cloud():
    """FastAPI dependency: raises 404 on self-hosted routes."""
    if is_self_hosted():
        raise HTTPException(status_code=404)


async def cloud_or_200():
    """FastAPI dependency: returns 200 no-op for webhooks in self-hosted mode."""
    if is_self_hosted():
        return Response(status_code=200)
