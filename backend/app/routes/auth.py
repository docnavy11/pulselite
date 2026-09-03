"""Authentication routes — login, register, logout, Google OAuth."""
import httpx
from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.auth_service import authenticate_user, register_user, delete_session, google_oauth_callback

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse("auth/login.html", {"request": request})


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
