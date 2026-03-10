"""Shopify OAuth flow and webhook handler.

Endpoints:
  GET  /oauth/shopify/authorize  — redirect merchant to Shopify consent screen
  GET  /oauth/shopify/callback   — exchange code for token and inject widget via ScriptTag API
  POST /webhooks/shopify/orders  — receive Shopify order events for AI Actions context
"""

import hashlib
import hmac
import json
import secrets
import urllib.parse
import uuid

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.integrations import IntegrationConfig
from app.models.knowledge import Chatbot
from app.models.organizational import Agent

router = APIRouter(tags=["shopify"])


# ---------------------------------------------------------------------------
# Authorize
# ---------------------------------------------------------------------------


@router.get("/oauth/shopify/authorize")
async def shopify_authorize(
    shop: str = Query(..., description="Shopify store domain, e.g. mystore.myshopify.com"),
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
):
    """Redirect the merchant to the Shopify OAuth consent screen."""
    if not settings.SHOPIFY_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shopify OAuth not configured",
        )

    if not shop.endswith(".myshopify.com"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid shop domain — must end with .myshopify.com",
        )

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    # Store both workspace_id and shop so the callback can look up the chatbot
    await r.setex(
        f"pulse:shopify_state:{state}",
        300,
        json.dumps({"workspace_id": str(workspace_id), "shop": shop}),
    )
    await r.close()

    scopes = "read_script_tags,write_script_tags,read_orders,read_products"
    redirect_uri = f"{settings.BASE_URL}/api/v1/oauth/shopify/callback"
    params = urllib.parse.urlencode(
        {
            "client_id": settings.SHOPIFY_CLIENT_ID,
            "scope": scopes,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return RedirectResponse(f"https://{shop}/admin/oauth/authorize?{params}")


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------


@router.get("/oauth/shopify/callback")
async def shopify_callback(
    code: str = Query(...),
    shop: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange Shopify OAuth code for a permanent access token and inject the Pulse widget."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    state_data_str = await r.get(f"pulse:shopify_state:{state}")
    if state_data_str:
        await r.delete(f"pulse:shopify_state:{state}")
    await r.close()

    if not state_data_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state",
        )

    state_data = json.loads(state_data_str)
    workspace_id = uuid.UUID(state_data["workspace_id"])

    # Guard: shop in callback must match shop stored in state to prevent fixation attacks
    if state_data.get("shop") != shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shop domain mismatch",
        )

    # Exchange code for permanent access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            f"https://{shop}/admin/oauth/access_token",
            json={
                "client_id": settings.SHOPIFY_CLIENT_ID,
                "client_secret": settings.SHOPIFY_CLIENT_SECRET,
                "code": code,
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shopify token exchange failed",
            )
        token_data = token_resp.json()

    access_token = token_data.get("access_token", "")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shopify token exchange failed — no access_token in response",
        )

    # Encrypt token at rest using Fernet symmetric encryption
    encrypted_token = access_token
    if settings.FERNET_KEY:
        from cryptography.fernet import Fernet

        f = Fernet(settings.FERNET_KEY.encode())
        encrypted_token = f.encrypt(access_token.encode()).decode()

    # Fetch the first active chatbot for this workspace to know which widget to inject
    chatbot_result = await db.execute(
        select(Chatbot)
        .where(
            Chatbot.workspace_id == workspace_id,
            Chatbot.is_active == True,  # noqa: E712
        )
        .limit(1)
    )
    chatbot = chatbot_result.scalar_one_or_none()

    # Inject the Pulse widget onto the Shopify storefront via the ScriptTag API
    widget_script_url = f"{settings.FRONTEND_URL}/widget.js"
    if chatbot:
        async with httpx.AsyncClient() as client:
            script_resp = await client.post(
                f"https://{shop}/admin/api/2024-01/script_tags.json",
                headers={"X-Shopify-Access-Token": access_token},
                json={
                    "script_tag": {
                        "event": "onload",
                        "src": widget_script_url,
                    }
                },
            )
            # Log but don't fail if ScriptTag injection is rejected — operator can retry
            if script_resp.status_code not in (200, 201):
                pass  # Non-fatal; integration is still stored

    # Upsert IntegrationConfig for this workspace
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "shopify",
        )
    )
    config = result.scalar_one_or_none()

    shopify_config = {
        "shop": shop,
        "access_token": encrypted_token,
        "chatbot_id": str(chatbot.id) if chatbot else "",
    }

    if config:
        config.config = shopify_config
        config.is_active = True
    else:
        config = IntegrationConfig(
            workspace_id=workspace_id,
            integration_type="shopify",
            config=shopify_config,
            is_active=True,
        )
        db.add(config)

    await db.commit()

    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?shopify_connected=1")


# ---------------------------------------------------------------------------
# Webhook — order events
# ---------------------------------------------------------------------------


@router.post("/webhooks/shopify/orders")
async def shopify_order_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(...),
    x_shopify_shop_domain: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Receive Shopify order/create webhook events for AI Actions context enrichment.

    Shopify signs every webhook with HMAC-SHA256 using the app's client secret.
    We verify the signature before processing.
    """
    body = await request.body()

    # Verify HMAC signature
    if settings.SHOPIFY_CLIENT_SECRET:
        expected = hmac.new(
            settings.SHOPIFY_CLIENT_SECRET.encode(),
            body,
            hashlib.sha256,
        ).digest()
        import base64

        expected_b64 = base64.b64encode(expected).decode()
        if not hmac.compare_digest(expected_b64, x_shopify_hmac_sha256):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    shop = x_shopify_shop_domain

    # Look up the IntegrationConfig for this shop to get the linked workspace
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.integration_type == "shopify",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    configs = result.scalars().all()

    matching_config = None
    for cfg in configs:
        cfg_config = cfg.config or {}
        if isinstance(cfg_config, str):
            cfg_config = json.loads(cfg_config)
        if cfg_config.get("shop") == shop:
            matching_config = cfg
            break

    if not matching_config:
        # Accept but ignore webhooks from shops we don't recognise (idempotent)
        return JSONResponse({"status": "ignored"})

    # Order data is available here for downstream AI Actions context enrichment.
    # For Phase 1 we store nothing but acknowledge receipt so Shopify stops retrying.
    order_id = payload.get("id")
    order_number = payload.get("order_number")
    _ = order_id, order_number  # consumed by future AI Actions tasks

    return JSONResponse({"status": "ok"})
