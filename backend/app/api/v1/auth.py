import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.api.v1.public_chat import limiter
from app.schemas.auth import AuthResponse, LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import auth_service
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
@limiter.limit("3/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    agent, _workspace, tokens = await auth_service.register_user(
        db, body.email, body.password, body.name, body.workspace_name
    )
    return AuthResponse(user=UserResponse.model_validate(agent), tokens=TokenResponse(**tokens))


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    from fastapi import status
    from app.services.encryption import decrypt_api_key
    import pyotp

    try:
        agent, tokens = await auth_service.authenticate_user(db, body.email, body.password)
    except HTTPException:
        await record_audit_event(
            db,
            workspace_id=None,
            action="auth.login_failed",
            user_email=body.email,
            ip_address=request.client.host if request.client else None,
            details={"reason": "invalid_credentials"},
        )
        await db.commit()
        raise

    # 2FA check: if enabled, require a valid TOTP code before issuing tokens
    if agent.two_fa_enabled:
        if not body.totp_code:
            # Signal to the frontend that a 2FA code is needed
            return JSONResponse(
                status_code=202,
                content={"requires_2fa": True},
            )
        # Verify the provided code
        try:
            if not agent.totp_secret:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="2FA not configured")
            secret = decrypt_api_key(agent.totp_secret)
            totp = pyotp.TOTP(secret)
            if not totp.verify(body.totp_code, valid_window=1):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid 2FA code",
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
            )

    await record_audit_event(
        db,
        workspace_id=agent.workspace_id,
        user_id=agent.id,
        user_email=agent.email,
        action="auth.login_success",
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return AuthResponse(user=UserResponse.model_validate(agent), tokens=TokenResponse(**tokens))


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(request: Request, body: RefreshRequest):
    return await auth_service.refresh_tokens(body.refresh_token)


@router.get("/google")
async def google_login():
    import secrets
    import redis.asyncio as aioredis

    state = secrets.token_urlsafe(32)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.setex(f"pulse:oauth_state:{state}", 300, "1")
    await r.close()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
    }
    query = urllib.parse.urlencode(params)
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str = Query(...), state: str = Query(...), db: AsyncSession = Depends(get_db)):
    import redis.asyncio as aioredis
    from fastapi import status

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    valid = await r.get(f"pulse:oauth_state:{state}")
    if valid:
        await r.delete(f"pulse:oauth_state:{state}")
    await r.close()
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state")
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        google_user = userinfo_resp.json()

    _agent, tokens = await auth_service.google_oauth_callback(db, google_user)
    return tokens
