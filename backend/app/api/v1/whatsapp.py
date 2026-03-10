"""WhatsApp Business Cloud API webhook — receive messages and reply via Pulse AI."""

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.integrations import IntegrationConfig
from app.models.knowledge import Chatbot

router = APIRouter(tags=["whatsapp"])


@router.get("/whatsapp/webhook")
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification — return the challenge as a plain integer."""
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/whatsapp/webhook")
async def whatsapp_events(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive inbound WhatsApp messages and reply via the Pulse resolution pipeline.

    Always returns HTTP 200 — Meta retries any non-200 response.
    """
    try:
        body = await request.body()
        payload = json.loads(body)

        # Navigate the Meta webhook envelope
        entries = payload.get("entry", [])
        if not entries:
            return {"status": "ok"}

        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                if not messages:
                    continue

                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id", "")

                for msg in messages:
                    # Only handle text messages; skip images, audio, etc.
                    if msg.get("type") != "text":
                        continue

                    sender_phone = msg.get("from", "")
                    message_text = msg.get("text", {}).get("body", "").strip()

                    if not sender_phone or not message_text:
                        continue

                    # Find the IntegrationConfig for this phone_number_id
                    result = await db.execute(
                        select(IntegrationConfig).where(
                            IntegrationConfig.integration_type == "whatsapp",
                            IntegrationConfig.is_active == True,  # noqa: E712
                        )
                    )
                    all_configs = result.scalars().all()

                    workspace_config = None
                    for cfg in all_configs:
                        if cfg.config.get("phone_number_id") == phone_number_id:
                            workspace_config = cfg
                            break

                    if not workspace_config:
                        continue  # No workspace connected to this WhatsApp number

                    # Decrypt the stored access token (Fernet-encrypted)
                    access_token = workspace_config.config.get("access_token", "")
                    if settings.FERNET_KEY and access_token:
                        from cryptography.fernet import Fernet

                        f = Fernet(settings.FERNET_KEY.encode())
                        access_token = f.decrypt(access_token.encode()).decode()

                    # Fall back to the global token if nothing stored per-config
                    token = access_token or settings.META_WHATSAPP_TOKEN

                    # Get the first active chatbot for this workspace
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

                    # Run the resolution pipeline and collect token stream
                    from app.services.resolution_service import handle_message

                    response_text = ""

                    async for event_obj in handle_message(
                        db=db,
                        workspace_id=workspace_config.workspace_id,
                        chatbot=chatbot,
                        message=message_text,
                        conversation_id=None,
                        contact_id=None,
                    ):
                        if event_obj.type == "token":
                            response_text += event_obj.data or ""

                    if not response_text:
                        response_text = "Sorry, I couldn't generate a response."

                    # Send the reply back via WhatsApp Cloud API
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"https://graph.facebook.com/v19.0/{phone_number_id}/messages",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "messaging_product": "whatsapp",
                                "to": sender_phone,
                                "type": "text",
                                "text": {"body": response_text},
                            },
                        )

    except Exception:
        # Swallow all errors — always return 200 so Meta doesn't retry
        pass

    return {"status": "ok"}
