import secrets
import uuid
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx
import redis.asyncio as aioredis
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent, WorkspaceMembership
from app.models.sso import SSOConfig
from app.services.audit import log_audit
from app.services.auth_service import _create_tokens

# Two routers: one for public /auth/sso/* routes, one for workspace-scoped routes
auth_router = APIRouter(prefix="/auth/sso", tags=["sso"])
workspace_router = APIRouter(prefix="/workspaces/{workspace_id}/sso", tags=["sso"])

SSO_STATE_PREFIX = "pulse:sso_state:"
SSO_STATE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SSOConfigBody(BaseModel):
    provider_name: str
    client_id: str
    client_secret: str
    discovery_url: str
    email_domain: str
    is_active: bool = True


class SSOConfigResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    provider_name: str
    client_id: str
    client_secret: str  # masked as "***" on reads
    discovery_url: str
    email_domain: str
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_https_url(url: str, field_name: str = "URL") -> None:
    """Raise HTTPException 400 if url is not https://."""
    scheme = urlparse(url).scheme
    if scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must use HTTPS (got '{scheme}://').",
        )


def _get_fernet() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY, str) else settings.FERNET_KEY)


def _encrypt_secret(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def _decrypt_secret(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


async def _fetch_discovery_doc(discovery_url: str) -> dict:
    """Fetch OIDC discovery document. Appends well-known path if not already present."""
    _validate_https_url(discovery_url, "Discovery URL")
    url = discovery_url
    if not url.endswith("openid-configuration"):
        url = url.rstrip("/") + "/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch OIDC discovery document: {exc}",
        )


async def _require_admin(
    workspace_id: uuid.UUID,
    current_user: Agent,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.agent_id == current_user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


# ---------------------------------------------------------------------------
# Public auth routes
# ---------------------------------------------------------------------------


@auth_router.get("/check")
async def sso_check(email: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Check whether an email address has SSO configured."""
    if "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address")

    domain = email.split("@", 1)[1].lower()
    result = await db.execute(
        select(SSOConfig).where(
            SSOConfig.email_domain == domain,
            SSOConfig.is_active.is_(True),
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        return {"has_sso": False, "provider_name": None, "workspace_id": None}

    return {
        "has_sso": True,
        "provider_name": config.provider_name,
        "workspace_id": str(config.workspace_id),
    }


@auth_router.get("/authorize")
async def sso_authorize(workspace_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)):
    """Initiate OIDC authorization flow for a workspace."""
    result = await db.execute(
        select(SSOConfig).where(
            SSOConfig.workspace_id == workspace_id,
            SSOConfig.is_active.is_(True),
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active SSO configuration for workspace")

    discovery = await _fetch_discovery_doc(config.discovery_url)
    authorization_endpoint = discovery.get("authorization_endpoint")
    if not authorization_endpoint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC discovery doc missing authorization_endpoint",
        )

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await r.setex(f"{SSO_STATE_PREFIX}{state}", SSO_STATE_TTL, str(workspace_id))
    finally:
        await r.aclose()

    redirect_uri = f"{settings.BASE_URL}/api/v1/auth/sso/callback"
    params = urlencode(
        {
            "client_id": config.client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return RedirectResponse(f"{authorization_endpoint}?{params}")


@auth_router.get("/callback")
async def sso_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle OIDC callback: exchange code, provision user, issue Pulse tokens."""
    # Verify state
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        workspace_id_str = await r.get(f"{SSO_STATE_PREFIX}{state}")
        if workspace_id_str:
            await r.delete(f"{SSO_STATE_PREFIX}{state}")
    finally:
        await r.aclose()

    if not workspace_id_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired SSO state")

    workspace_id = uuid.UUID(workspace_id_str)

    # Load SSO config
    result = await db.execute(
        select(SSOConfig).where(
            SSOConfig.workspace_id == workspace_id,
            SSOConfig.is_active.is_(True),
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SSO configuration not found or inactive")

    client_secret = _decrypt_secret(config.client_secret)

    # Fetch discovery doc for endpoints
    discovery = await _fetch_discovery_doc(config.discovery_url)
    token_endpoint = discovery.get("token_endpoint", "")
    userinfo_endpoint = discovery.get("userinfo_endpoint", "")
    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC discovery doc missing token_endpoint",
        )
    # Validate endpoints from discovery doc to prevent second-order SSRF
    _validate_https_url(token_endpoint, "token_endpoint")
    if userinfo_endpoint:
        _validate_https_url(userinfo_endpoint, "userinfo_endpoint")
    if not userinfo_endpoint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC discovery doc missing userinfo_endpoint",
        )

    redirect_uri = f"{settings.BASE_URL}/api/v1/auth/sso/callback"

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Exchange authorization code for tokens
        token_resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": config.client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
        )
        if token_resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Token exchange failed: {token_resp.text}",
            )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No access_token in IdP response")

        # Fetch userinfo
        userinfo_resp = await client.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Userinfo request failed: {userinfo_resp.text}",
            )
        userinfo = userinfo_resp.json()

    email: Optional[str] = userinfo.get("email")
    name: str = userinfo.get("name") or userinfo.get("given_name") or (email.split("@")[0] if email else "Unknown")

    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="IdP did not return an email address")

    # Find or create Agent
    agent_result = await db.execute(select(Agent).where(Agent.email == email))
    agent = agent_result.scalar_one_or_none()

    if agent is None:
        # New user — create agent
        agent = Agent(
            email=email,
            name=name,
            password_hash=None,
        )
        db.add(agent)
        await db.flush()

        # Create membership
        membership = WorkspaceMembership(
            agent_id=agent.id,
            workspace_id=workspace_id,
            role="member",
        )
        db.add(membership)
        await db.flush()
    else:
        # Existing user — ensure membership exists for this workspace
        mem_result = await db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.agent_id == agent.id,
            )
        )
        existing_membership = mem_result.scalar_one_or_none()
        if existing_membership is None:
            membership = WorkspaceMembership(
                agent_id=agent.id,
                workspace_id=workspace_id,
                role="member",
            )
            db.add(membership)
            await db.flush()

    await db.commit()
    await db.refresh(agent)

    # Issue Pulse JWT pair
    tokens = await _create_tokens(agent)

    # Redirect to frontend with tokens
    frontend_url = settings.FRONTEND_URL
    redirect_url = (
        f"{frontend_url}/auth/sso/complete"
        f"?access_token={tokens['access_token']}"
        f"&refresh_token={tokens['refresh_token']}"
    )
    return RedirectResponse(redirect_url)


# ---------------------------------------------------------------------------
# Authenticated workspace routes
# ---------------------------------------------------------------------------


@workspace_router.get("", response_model=SSOConfigResponse)
async def get_sso_config(
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return SSO configuration for the workspace (client_secret masked)."""
    result = await db.execute(select(SSOConfig).where(SSOConfig.workspace_id == workspace_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SSO configuration found")

    return SSOConfigResponse(
        id=config.id,
        workspace_id=config.workspace_id,
        provider_name=config.provider_name,
        client_id=config.client_id,
        client_secret="***",
        discovery_url=config.discovery_url,
        email_domain=config.email_domain,
        is_active=config.is_active,
    )


@workspace_router.put("", response_model=SSOConfigResponse)
async def upsert_sso_config(
    request: Request,
    body: SSOConfigBody,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update SSO configuration for the workspace. Admin only."""
    await _require_admin(workspace_id, current_user, db)

    # Validate discovery URL — HTTPS required (SSRF prevention)
    _validate_https_url(body.discovery_url, "Discovery URL")

    encrypted_secret = _encrypt_secret(body.client_secret)

    result = await db.execute(select(SSOConfig).where(SSOConfig.workspace_id == workspace_id))
    config = result.scalar_one_or_none()

    if config is None:
        config = SSOConfig(
            workspace_id=workspace_id,
            provider_name=body.provider_name,
            client_id=body.client_id,
            client_secret=encrypted_secret,
            discovery_url=body.discovery_url,
            email_domain=body.email_domain.lower(),
            is_active=body.is_active,
        )
        db.add(config)
    else:
        config.provider_name = body.provider_name
        config.client_id = body.client_id
        config.client_secret = encrypted_secret
        config.discovery_url = body.discovery_url
        config.email_domain = body.email_domain.lower()
        config.is_active = body.is_active

    await log_audit(
        db,
        workspace_id,
        "sso.update",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="sso",
        resource_id=str(workspace_id),
        ip_address=request.client.host if request.client else None,
        metadata={"provider_name": body.provider_name, "email_domain": body.email_domain},
    )
    await db.commit()
    await db.refresh(config)

    return SSOConfigResponse(
        id=config.id,
        workspace_id=config.workspace_id,
        provider_name=config.provider_name,
        client_id=config.client_id,
        client_secret="***",
        discovery_url=config.discovery_url,
        email_domain=config.email_domain,
        is_active=config.is_active,
    )


@workspace_router.delete("", status_code=status.HTTP_200_OK)
async def disable_sso_config(
    request: Request,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable (soft-delete) SSO configuration for the workspace. Admin only."""
    await _require_admin(workspace_id, current_user, db)

    result = await db.execute(select(SSOConfig).where(SSOConfig.workspace_id == workspace_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SSO configuration found")

    config.is_active = False
    await log_audit(
        db,
        workspace_id,
        "sso.delete",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="sso",
        resource_id=str(workspace_id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return {"detail": "SSO configuration disabled"}
