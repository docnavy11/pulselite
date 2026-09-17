"""Authentication routes — login, register, logout, Google OAuth, workspace switching."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.auth_service import authenticate_user, register_user, delete_session, google_oauth_callback

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse("auth/login.html", {
        "request": request, "google_oauth": bool(settings.GOOGLE_CLIENT_ID),
    })


@router.post("/login")
async def login(
    request: Request, email: str = Form(...), password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        agent, session = await authenticate_user(
            db, email, password, ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        return request.app.state.templates.TemplateResponse("auth/login.html", {
            "request": request, "error": "Invalid email or password",
        }, status_code=401)

    # Check 2FA
    if agent.two_fa_enabled:
        response = request.app.state.templates.TemplateResponse("auth/2fa.html", {
            "request": request, "session_id": session.id,
        })
        return response

    response = RedirectResponse("/chatbots", status_code=303)
    response.set_cookie("session_id", session.id, httponly=True, samesite="lax", max_age=settings.SESSION_EXPIRY_DAYS * 86400)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return request.app.state.templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
async def register(
    request: Request, email: str = Form(...), password: str = Form(...),
    name: str = Form(...), workspace_name: str = Form("My Workspace"),
    db: AsyncSession = Depends(get_db),
):
    try:
        agent, workspace, session = await register_user(
            db, email, password, name, workspace_name,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as e:
        return request.app.state.templates.TemplateResponse("auth/register.html", {
            "request": request, "error": str(e.detail) if hasattr(e, "detail") else str(e),
        }, status_code=409)

    response = RedirectResponse("/chatbots", status_code=303)
    response.set_cookie("session_id", session.id, httponly=True, samesite="lax", max_age=settings.SESSION_EXPIRY_DAYS * 86400)
    return response


@router.post("/workspaces/switch")
async def switch_workspace(
    request: Request,
    workspace_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Switch the current session to a different workspace."""
    from app.models.organizational import WorkspaceMembership, Workspace
    from app.models.session import Session

    user = request.state.user
    # Verify the user is actually a member of the target workspace
    membership = (await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.agent_id == user.id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )).scalar_one_or_none()
    if not membership:
        return RedirectResponse("/dashboard", status_code=303)

    # Update the session's workspace_id in-place
    session_id = request.cookies.get("session_id")
    await db.execute(
        sa_update(Session)
        .where(Session.id == session_id)
        .values(workspace_id=workspace_id)
    )
    await db.commit()

    # Redirect back to wherever they were (or dashboard)
    referer = request.headers.get("referer", "/dashboard")
    return RedirectResponse(referer, status_code=303)


@router.post("/workspaces/new")
async def create_workspace(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace and switch to it."""
    import re
    from app.models.organizational import Workspace, WorkspaceMembership
    from app.models.session import Session

    user = request.state.user
    name = name.strip()[:100]
    if not name:
        return RedirectResponse("/dashboard", status_code=303)

    # Generate slug
    slug_base = re.sub(r"[^a-z0-9-]", "-", name.lower())
    slug_base = re.sub(r"-+", "-", slug_base).strip("-") or "workspace"
    slug = f"{slug_base}-{secrets.token_hex(3)}"

    new_ws = Workspace(id=uuid.uuid4(), name=name, slug=slug)
    db.add(new_ws)
    await db.flush()

    membership = WorkspaceMembership(id=uuid.uuid4(), agent_id=user.id, workspace_id=new_ws.id, role="owner")
    db.add(membership)
    await db.flush()

    # Update current session to point to new workspace
    session_id = request.cookies.get("session_id")
    await db.execute(
        sa_update(Session)
        .where(Session.id == session_id)
        .values(workspace_id=new_ws.id)
    )
    await db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id:
        await delete_session(db, session_id)
        await db.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_id")
    return response


@router.get("/auth/google")
async def google_oauth_start():
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url)


@router.get("/auth/google/callback")
async def google_oauth_callback_route(request: Request, code: str, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI, "grant_type": "authorization_code",
        })
        tokens = token_resp.json()
        userinfo_resp = await client.get("https://www.googleapis.com/oauth2/v3/userinfo",
                                          headers={"Authorization": f"Bearer {tokens['access_token']}"})
        google_user = userinfo_resp.json()

    agent, session = await google_oauth_callback(
        db, google_user, ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    response = RedirectResponse("/chatbots", status_code=303)
    response.set_cookie("session_id", session.id, httponly=True, samesite="lax", max_age=settings.SESSION_EXPIRY_DAYS * 86400)
    return response
