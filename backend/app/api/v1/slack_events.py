"""Slack Events API webhook — receives messages and routes them to the resolution pipeline."""

import hashlib
import hmac
import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.integrations import IntegrationConfig

router = APIRouter(tags=["slack"])


def _verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify that the request came from Slack using the signing secret."""
    if not settings.SLACK_SIGNING_SECRET:
        return True  # Skip verification if not configured (dev mode)
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False  # Replay attack protection
    except ValueError:
        return False
    sig_basestring = f"v0:{timestamp}:{request_body.decode()}"
    computed = (
        "v0="
        + hmac.new(
            settings.SLACK_SIGNING_SECRET.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(computed, signature)


@router.post("/slack/events")
async def slack_events(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_signature(body, timestamp, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack signature",
        )

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return {"ok": True}

    # URL verification challenge (Slack sends this when you first configure the Events URL)
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    event = payload.get("event", {})
    event_type = event.get("type")
    team_id = payload.get("team_id", "")

    # Only handle direct messages and app mentions
    if event_type not in ("message", "app_mention"):
        return {"ok": True}

    # Skip bot messages (avoid infinite loops)
    if event.get("bot_id") or event.get("subtype"):
        return {"ok": True}

    text = event.get("text", "").strip()
    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts")
    event.get("user", "")

    if not text or not channel:
        return {"ok": True}

    # Find the workspace that has this Slack team connected
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.integration_type == "slack_bot",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    all_configs = result.scalars().all()

    workspace_config = None
    for cfg in all_configs:
        if cfg.config.get("team_id") == team_id:
            workspace_config = cfg
            break

    if not workspace_config:
        return {"ok": True}  # No workspace configured for this Slack team

    # Decrypt bot token
    bot_token = workspace_config.config.get("bot_token", "")
    if settings.FERNET_KEY and bot_token:
        from cryptography.fernet import Fernet

        f = Fernet(settings.FERNET_KEY.encode())
        bot_token = f.decrypt(bot_token.encode()).decode()

    # Get the first active chatbot for this workspace to use as the AI agent
    from app.models.knowledge import Chatbot

    chatbot_result = await db.execute(
        select(Chatbot)
        .where(
            Chatbot.workspace_id == workspace_config.workspace_id,
            Chatbot.is_active == True,  # noqa: E712
        )
        .limit(1)
    )
    chatbot = chatbot_result.scalar_one_or_none()
    if not chatbot:
        return {"ok": True}

    # Call the resolution pipeline (non-streaming — collect full response)
    from app.services.resolution_service import handle_message

    response_text = ""

    async for event_obj in handle_message(
        db=db,
        workspace_id=workspace_config.workspace_id,
        chatbot=chatbot,
        message=text,
        conversation_id=None,
        contact_id=None,
    ):
        if event_obj.type == "token":
            response_text += event_obj.data or ""

    if not response_text:
        response_text = "Sorry, I couldn't generate a response."

    # Post reply to Slack
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {bot_token}"},
            json={
                "channel": channel,
                "thread_ts": thread_ts,
                "text": response_text,
            },
        )

    return {"ok": True}
