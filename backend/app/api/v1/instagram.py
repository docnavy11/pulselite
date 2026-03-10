"""Instagram DM webhook — receives messages via the Messenger platform API and routes them to the resolution pipeline."""

import httpx
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.integrations import IntegrationConfig

router = APIRouter(tags=["instagram"])


@router.get("/instagram/webhook")
async def instagram_webhook_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """Meta webhook verification handshake."""
    if hub_mode == "subscribe" and hub_verify_token == settings.META_INSTAGRAM_VERIFY_TOKEN:
        return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge
    return {"status": "forbidden"}


@router.post("/instagram/webhook")
async def instagram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Instagram DM events and route them through the resolution pipeline."""
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ok"}

    for entry in payload.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id: str = messaging.get("sender", {}).get("id", "")
            recipient_id: str = messaging.get("recipient", {}).get("id", "")
            message: dict = messaging.get("message", {})

            # Skip if no text payload
            text: str = message.get("text", "").strip()
            if not text:
                continue

            # Skip echo messages (messages sent by the page itself)
            if message.get("is_echo"):
                continue

            # Look up the IntegrationConfig for this Instagram Business Account
            result = await db.execute(
                select(IntegrationConfig).where(
                    IntegrationConfig.integration_type == "instagram",
                    IntegrationConfig.is_active == True,  # noqa: E712
                )
            )
            all_configs = result.scalars().all()

            workspace_config: IntegrationConfig | None = None
            for cfg in all_configs:
                if cfg.config.get("account_id") == recipient_id:
                    workspace_config = cfg
                    break

            if not workspace_config:
                continue

            # Decrypt page access token
            page_access_token: str = workspace_config.config.get("page_access_token", "")
            if settings.FERNET_KEY and page_access_token:
                from cryptography.fernet import Fernet

                f = Fernet(settings.FERNET_KEY.encode())
                page_access_token = f.decrypt(page_access_token.encode()).decode()

            # Get the first active chatbot for this workspace
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
                continue

            # Run the resolution pipeline (non-streaming — collect full response)
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

            # Reply via Instagram Messaging API
            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://graph.facebook.com/v19.0/me/messages",
                    params={"access_token": page_access_token},
                    json={
                        "recipient": {"id": sender_id},
                        "message": {"text": response_text},
                    },
                )

    return {"status": "ok"}
