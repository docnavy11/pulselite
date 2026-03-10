"""OAuth flows for third-party integrations (Notion, etc.)"""

import base64
import json
import secrets
import urllib.parse
import uuid

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.integrations import IntegrationConfig
from app.models.organizational import Agent

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.get("/notion/authorize")
async def notion_authorize(
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
):
    """Redirect user to Notion OAuth consent screen."""
    if not settings.NOTION_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notion OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    # Store workspace_id in state so callback knows who to credit
    await r.setex(f"pulse:notion_state:{state}", 300, str(workspace_id))
    await r.close()

    params = urllib.parse.urlencode(
        {
            "client_id": settings.NOTION_CLIENT_ID,
            "redirect_uri": settings.NOTION_REDIRECT_URI,
            "response_type": "code",
            "state": state,
        }
    )
    return RedirectResponse(f"https://api.notion.com/v1/oauth/authorize?{params}&owner=user")


@router.get("/notion/callback")
async def notion_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange Notion OAuth code for access token and store in IntegrationConfig."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    workspace_id_str = await r.get(f"pulse:notion_state:{state}")
    if workspace_id_str:
        await r.delete(f"pulse:notion_state:{state}")
    await r.close()

    if not workspace_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    workspace_id = uuid.UUID(workspace_id_str)

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        credentials = base64.b64encode(f"{settings.NOTION_CLIENT_ID}:{settings.NOTION_CLIENT_SECRET}".encode()).decode()
        token_resp = await client.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.NOTION_REDIRECT_URI,
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Notion token exchange failed",
            )
        token_data = token_resp.json()

    access_token = token_data.get("access_token", "")

    # Encrypt and store in IntegrationConfig
    encrypted_token = access_token
    if settings.FERNET_KEY and access_token:
        from cryptography.fernet import Fernet

        f = Fernet(settings.FERNET_KEY.encode())
        encrypted_token = f.encrypt(access_token.encode()).decode()

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "notion",
        )
    )
    config = result.scalar_one_or_none()
    notion_config = {
        "access_token": encrypted_token,
        "bot_id": token_data.get("bot_id", ""),
        "workspace_name": token_data.get("workspace_name", ""),
    }
    if config:
        config.config = notion_config
        config.is_active = True
    else:
        config = IntegrationConfig(
            workspace_id=workspace_id,
            integration_type="notion",
            config=notion_config,
            is_active=True,
        )
        db.add(config)

    await db.commit()

    # Redirect back to integrations settings page
    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?connected=notion")


@router.get("/slack/authorize")
async def slack_authorize(
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
):
    """Redirect user to Slack OAuth consent screen to install the bot."""
    if not settings.SLACK_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack bot OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.setex(f"pulse:slack_state:{state}", 300, str(workspace_id))
    await r.close()

    params = urllib.parse.urlencode(
        {
            "client_id": settings.SLACK_CLIENT_ID,
            "scope": settings.SLACK_BOT_SCOPE,
            "redirect_uri": settings.BASE_URL + "/api/v1/oauth/slack/callback",
            "state": state,
        }
    )
    return RedirectResponse(f"https://slack.com/oauth/v2/authorize?{params}")


@router.get("/slack/callback")
async def slack_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange Slack OAuth code for bot token and store in IntegrationConfig."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    workspace_id_str = await r.get(f"pulse:slack_state:{state}")
    if workspace_id_str:
        await r.delete(f"pulse:slack_state:{state}")
    await r.close()

    if not workspace_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    workspace_id = uuid.UUID(workspace_id_str)

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.BASE_URL + "/api/v1/oauth/slack/callback",
            },
        )
        token_data = token_resp.json()

    if not token_data.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slack OAuth failed: {token_data.get('error')}",
        )

    bot_token = token_data.get("access_token", "")
    team_name = token_data.get("team", {}).get("name", "")
    team_id = token_data.get("team", {}).get("id", "")
    bot_user_id = token_data.get("bot_user_id", "")

    encrypted_token = bot_token
    if settings.FERNET_KEY and bot_token:
        from cryptography.fernet import Fernet

        f = Fernet(settings.FERNET_KEY.encode())
        encrypted_token = f.encrypt(bot_token.encode()).decode()

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "slack_bot",
        )
    )
    config = result.scalar_one_or_none()
    slack_config = {
        "bot_token": encrypted_token,
        "team_name": team_name,
        "team_id": team_id,
        "bot_user_id": bot_user_id,
    }
    if config:
        config.config = slack_config
        config.is_active = True
    else:
        config = IntegrationConfig(
            workspace_id=workspace_id,
            integration_type="slack_bot",
            config=slack_config,
            is_active=True,
        )
        db.add(config)

    await db.commit()

    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?slack_connected=1")


@router.get("/zendesk/authorize")
async def zendesk_authorize(
    workspace_id: uuid.UUID = Depends(get_workspace),
    subdomain: str = Query(...),
    current_user: Agent = Depends(get_current_user),
):
    """Redirect user to Zendesk OAuth consent screen."""
    if not settings.ZENDESK_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zendesk OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    # Store workspace_id and subdomain in Redis keyed by state
    await r.setex(
        f"pulse:zendesk_state:{state}",
        300,
        json.dumps({"workspace_id": str(workspace_id), "subdomain": subdomain}),
    )
    await r.close()

    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "redirect_uri": f"{settings.BASE_URL}/api/v1/oauth/zendesk/callback",
            "client_id": settings.ZENDESK_CLIENT_ID,
            "scope": "read",
            "state": state,
            "subdomain": subdomain,
        }
    )
    return RedirectResponse(f"https://{subdomain}.zendesk.com/oauth/authorizations/new?{params}")


@router.get("/zendesk/callback")
async def zendesk_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange Zendesk OAuth code for access token and store in IntegrationConfig."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    state_json = await r.get(f"pulse:zendesk_state:{state}")
    if state_json:
        await r.delete(f"pulse:zendesk_state:{state}")
    await r.close()

    if not state_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    state_data = json.loads(state_json)
    workspace_id = uuid.UUID(state_data["workspace_id"])
    subdomain = state_data["subdomain"]

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            f"https://{subdomain}.zendesk.com/oauth/tokens",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.ZENDESK_CLIENT_ID,
                "client_secret": settings.ZENDESK_CLIENT_SECRET,
                "redirect_uri": f"{settings.BASE_URL}/api/v1/oauth/zendesk/callback",
                "scope": "read",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Zendesk token exchange failed",
            )
        token_data = token_resp.json()

    access_token = token_data.get("access_token", "")

    # Optionally encrypt the access token
    encrypted_token = access_token
    if settings.FERNET_KEY and access_token:
        from cryptography.fernet import Fernet

        f = Fernet(settings.FERNET_KEY.encode())
        encrypted_token = f.encrypt(access_token.encode()).decode()

    zendesk_config = {
        "subdomain": subdomain,
        "access_token": encrypted_token,
    }

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "zendesk",
        )
    )
    config = result.scalar_one_or_none()
    if config:
        config.config = zendesk_config
        config.is_active = True
    else:
        config = IntegrationConfig(
            workspace_id=workspace_id,
            integration_type="zendesk",
            config=zendesk_config,
            is_active=True,
        )
        db.add(config)

    await db.commit()

    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?connected=zendesk")


@router.get("/dropbox/authorize")
async def dropbox_authorize(
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
):
    """Redirect user to Dropbox OAuth consent screen."""
    if not settings.DROPBOX_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dropbox OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.setex(f"pulse:dropbox_state:{state}", 300, str(workspace_id))
    await r.close()

    params = urllib.parse.urlencode(
        {
            "client_id": settings.DROPBOX_CLIENT_ID,
            "redirect_uri": f"{settings.BASE_URL}/api/v1/oauth/dropbox/callback",
            "response_type": "code",
            "token_access_type": "offline",
            "state": state,
        }
    )
    return RedirectResponse(f"https://www.dropbox.com/oauth2/authorize?{params}")


@router.get("/dropbox/callback")
async def dropbox_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange Dropbox OAuth code for access token and store in IntegrationConfig."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    workspace_id_str = await r.get(f"pulse:dropbox_state:{state}")
    if workspace_id_str:
        await r.delete(f"pulse:dropbox_state:{state}")
    await r.close()

    if not workspace_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    workspace_id = uuid.UUID(workspace_id_str)

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://api.dropboxapi.com/oauth2/token",
            data={
                "code": code,
                "grant_type": "authorization_code",
                "client_id": settings.DROPBOX_CLIENT_ID,
                "client_secret": settings.DROPBOX_CLIENT_SECRET,
                "redirect_uri": f"{settings.BASE_URL}/api/v1/oauth/dropbox/callback",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dropbox token exchange failed",
            )
        token_data = token_resp.json()

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    account_id = token_data.get("account_id", "")

    # Encrypt the access token
    encrypted_access_token = access_token
    if settings.FERNET_KEY and access_token:
        from cryptography.fernet import Fernet

        f = Fernet(settings.FERNET_KEY.encode())
        encrypted_access_token = f.encrypt(access_token.encode()).decode()

    dropbox_config = {
        "access_token": encrypted_access_token,
        "refresh_token": refresh_token,
        "account_id": account_id,
    }

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "dropbox",
        )
    )
    config = result.scalar_one_or_none()
    if config:
        config.config = dropbox_config
        config.is_active = True
    else:
        config = IntegrationConfig(
            workspace_id=workspace_id,
            integration_type="dropbox",
            config=dropbox_config,
            is_active=True,
        )
        db.add(config)

    await db.commit()

    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?connected=dropbox")


@router.get("/salesforce/authorize")
async def salesforce_authorize(
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
):
    """Redirect user to Salesforce OAuth consent screen."""
    if not settings.SALESFORCE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Salesforce OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.setex(f"pulse:salesforce_state:{state}", 300, str(workspace_id))
    await r.close()

    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": settings.SALESFORCE_CLIENT_ID,
            "redirect_uri": f"{settings.BASE_URL}/api/v1/oauth/salesforce/callback",
            "scope": "api refresh_token",
            "state": state,
        }
    )
    return RedirectResponse(f"https://login.salesforce.com/services/oauth2/authorize?{params}")


@router.get("/salesforce/callback")
async def salesforce_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange Salesforce OAuth code for access token and store in IntegrationConfig."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    workspace_id_str = await r.get(f"pulse:salesforce_state:{state}")
    if workspace_id_str:
        await r.delete(f"pulse:salesforce_state:{state}")
    await r.close()

    if not workspace_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    workspace_id = uuid.UUID(workspace_id_str)

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://login.salesforce.com/services/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.SALESFORCE_CLIENT_ID,
                "client_secret": settings.SALESFORCE_CLIENT_SECRET,
                "redirect_uri": f"{settings.BASE_URL}/api/v1/oauth/salesforce/callback",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Salesforce token exchange failed",
            )
        token_data = token_resp.json()

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    instance_url = token_data.get("instance_url", "")

    # Encrypt the access token
    encrypted_token = access_token
    if settings.FERNET_KEY and access_token:
        from cryptography.fernet import Fernet

        f = Fernet(settings.FERNET_KEY.encode())
        encrypted_token = f.encrypt(access_token.encode()).decode()

    salesforce_config = {
        "access_token": encrypted_token,
        "refresh_token": refresh_token,
        "instance_url": instance_url,
    }

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "salesforce",
        )
    )
    config = result.scalar_one_or_none()
    if config:
        config.config = salesforce_config
        config.is_active = True
    else:
        config = IntegrationConfig(
            workspace_id=workspace_id,
            integration_type="salesforce",
            config=salesforce_config,
            is_active=True,
        )
        db.add(config)

    await db.commit()

    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?connected=salesforce")


@router.get("/google/authorize")
async def google_drive_authorize(
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
):
    """Redirect user to Google OAuth consent screen for Drive access."""
    if not settings.GOOGLE_DRIVE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Drive OAuth not configured",
        )

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.setex(f"pulse:google_state:{state}", 300, str(workspace_id))
    await r.close()

    params = urllib.parse.urlencode(
        {
            "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
            "redirect_uri": f"{settings.BASE_URL}/api/v1/oauth/google/callback",
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/drive.readonly",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_drive_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange Google OAuth code for tokens and store in IntegrationConfig."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    workspace_id_str = await r.get(f"pulse:google_state:{state}")
    if workspace_id_str:
        await r.delete(f"pulse:google_state:{state}")
    await r.close()

    if not workspace_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    workspace_id = uuid.UUID(workspace_id_str)

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
                "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{settings.BASE_URL}/api/v1/oauth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google token exchange failed",
            )
        token_data = token_resp.json()

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")

    encrypted_access_token = access_token
    encrypted_refresh_token = refresh_token
    if settings.FERNET_KEY:
        from cryptography.fernet import Fernet

        f = Fernet(settings.FERNET_KEY.encode())
        if access_token:
            encrypted_access_token = f.encrypt(access_token.encode()).decode()
        if refresh_token:
            encrypted_refresh_token = f.encrypt(refresh_token.encode()).decode()

    google_config = {
        "access_token": encrypted_access_token,
        "refresh_token": encrypted_refresh_token,
        "token_type": token_data.get("token_type", "Bearer"),
    }

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "google_drive",
        )
    )
    config = result.scalar_one_or_none()
    if config:
        config.config = google_config
        config.is_active = True
    else:
        config = IntegrationConfig(
            workspace_id=workspace_id,
            integration_type="google_drive",
            config=google_config,
            is_active=True,
        )
        db.add(config)

    await db.commit()

    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?connected=google_drive")
