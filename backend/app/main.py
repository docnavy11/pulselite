from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import (
    actions,
    articles,
    auth,
    billing,
    chat,
    chatbots,
    config as config_router,
    copilot,
    crawl,
    dashboard,
    documents,
    gaps,
    gdpr,
    health,
    integrations,
    intelligence,
    invites,
    knowledge_bases,
    logs,
    oauth,
    onboarding,
    public_chat,
    qa,
    two_fa,
    webhooks,
    widget_config,
    workspaces,
)
from app.api.v1 import realtime as realtime_api
from app.api.v1.public_chat import limiter
from app.config import settings

import socketio as socketio_lib
from app.utils.security import decode_token
from app.services.realtime import mark_api_process

mark_api_process()

# Socket.IO server — in-memory manager (single-process deployment).
# Worker events reach clients via the internal HTTP emit endpoint.
sio = socketio_lib.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins,
    logger=False,
    engineio_logger=False,
)


async def _sio_connect(sid: str, environ: dict, auth_data: dict | None) -> None:
    """Authenticate Socket.IO connections via JWT."""
    token = auth_data.get("token") if auth_data else None
    if not token:
        raise socketio_lib.exceptions.ConnectionRefusedError("Missing token")
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise socketio_lib.exceptions.ConnectionRefusedError("Invalid token")
    await sio.save_session(sid, {"user_id": payload["sub"]})


sio.on("connect", _sio_connect)


@sio.event
async def join_workspace(sid: str, data: dict) -> None:
    """Join a workspace room after verifying membership."""
    import uuid
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.models.organizational import WorkspaceMembership

    workspace_id = data.get("workspace_id")
    if not workspace_id:
        return
    session_data = await sio.get_session(sid)
    user_id = session_data.get("user_id")
    if not user_id:
        return
    # Verify workspace membership
    async with async_session_factory() as db:
        result = await db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == uuid.UUID(str(workspace_id)),
                WorkspaceMembership.agent_id == uuid.UUID(str(user_id)),
            )
        )
        if result.scalar_one_or_none() is None:
            return  # silently reject — not a member
    await sio.enter_room(sid, str(workspace_id))


@sio.event
async def leave_workspace(sid: str, data: dict) -> None:
    workspace_id = data.get("workspace_id")
    if workspace_id:
        await sio.leave_room(sid, str(workspace_id))


def _run_preflight_checks(logger) -> list[str]:
    """Validate configuration at startup and log actionable warnings. Returns list of warnings."""
    warnings: list[str] = []

    # Security keys
    if "change-in-production" in settings.SECRET_KEY:
        msg = "SECRET_KEY is using the default dev value. Generate a secure key for production: python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
        logger.warning(msg)
        warnings.append(msg)

    if "change-in-production" in settings.JWT_SECRET_KEY:
        msg = "JWT_SECRET_KEY is using the default dev value. Generate a secure key for production."
        logger.warning(msg)
        warnings.append(msg)

    # Fernet key
    if not settings.FERNET_KEY:
        msg = "FERNET_KEY is not set. Encrypted API key storage will fail. Generate one: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        logger.error(msg)
        warnings.append(msg)
    else:
        try:
            from cryptography.fernet import Fernet
            Fernet(settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY, str) else settings.FERNET_KEY)
        except Exception:
            msg = "FERNET_KEY is invalid (not a valid Fernet key). Encrypted API key storage will fail. Generate a new one: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            logger.error(msg)
            warnings.append(msg)

    # Admin account
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        msg = "ADMIN_EMAIL/ADMIN_PASSWORD not set. No admin account will be created on first startup. Set these in .env to enable automatic admin bootstrapping."
        logger.warning(msg)
        warnings.append(msg)

    # AI configuration
    if not settings.AI_API_KEY:
        msg = "AI_API_KEY is not set. Chatbots will not work until you configure an AI provider (in .env or Settings > AI Models in the UI)."
        logger.warning(msg)
        warnings.append(msg)
    elif not settings.AI_BASE_URL:
        msg = "AI_API_KEY is set but AI_BASE_URL is empty. You must also set AI_BASE_URL (e.g. https://openrouter.ai/api/v1) for the AI provider to work."
        logger.warning(msg)
        warnings.append(msg)

    return warnings


def create_app() -> FastAPI:
    application = FastAPI(title="Pulselite API", version="0.1.0", docs_url="/api/docs", redoc_url="/api/redoc")

    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Authenticated routes
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(two_fa.router, prefix="/api/v1")
    application.include_router(workspaces.router, prefix="/api/v1")
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(chatbots.router, prefix="/api/v1")
    application.include_router(actions.router, prefix="/api/v1")
    application.include_router(knowledge_bases.router, prefix="/api/v1")
    application.include_router(documents.router, prefix="/api/v1")
    application.include_router(articles.router, prefix="/api/v1")
    application.include_router(crawl.router, prefix="/api/v1")
    application.include_router(logs.router, prefix="/api/v1")
    application.include_router(chat.router, prefix="/api/v1")
    application.include_router(intelligence.router, prefix="/api/v1")
    application.include_router(gaps.router, prefix="/api/v1")
    application.include_router(dashboard.router, prefix="/api/v1")
    application.include_router(integrations.router, prefix="/api/v1")
    application.include_router(billing.router, prefix="/api/v1")
    application.include_router(onboarding.router, prefix="/api/v1")
    application.include_router(gdpr.router, prefix="/api/v1")
    application.include_router(invites.router, prefix="/api/v1")
    application.include_router(webhooks.router, prefix="/api/v1")
    application.include_router(copilot.router, prefix="/api/v1")
    application.include_router(qa.router, prefix="/api/v1")
    application.include_router(realtime_api.router, prefix="/api/v1")

    # Public routes (no auth required)
    application.include_router(config_router.router, prefix="/api/v1")
    application.include_router(widget_config.router, prefix="/api/v1")
    application.include_router(public_chat.router, prefix="/api/v1")
    application.include_router(oauth.router, prefix="/api/v1")

    # Internal endpoint for workers to emit Socket.IO events.
    # Workers call this via HTTP — the only reliable cross-process path.
    @application.post("/api/internal/emit")
    async def internal_emit(request: Request):
        secret = request.headers.get("X-Internal-Secret")
        if secret != settings.SECRET_KEY:
            raise HTTPException(status_code=403, detail="Unauthorized")
        body = await request.json()
        await sio.emit(
            body["event"],
            body["data"],
            room=body.get("room"),
        )
        return {"ok": True}

    @application.on_event("startup")
    async def _startup():
        import logging
        _logger = logging.getLogger("pulse.startup")

        from app.services.plan_service import load_plan_tiers
        from app.services.bootstrap import bootstrap_admin

        # Pre-flight: validate critical config before anything else
        _preflight_warnings = _run_preflight_checks(_logger)

        try:
            await bootstrap_admin()
        except Exception as exc:
            _logger.error(
                "Failed to bootstrap admin user: %s. "
                "Check your database connection (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD) "
                "and ensure migrations have been run (make migrate).",
                exc,
            )

        try:
            await load_plan_tiers()
        except Exception as exc:
            _logger.warning("Failed to load plan tiers: %s — billing features may not work.", exc)

        # Print summary
        if _preflight_warnings:
            _logger.warning(
                "Startup completed with %d warning(s) — review messages above.",
                len(_preflight_warnings),
            )
        else:
            _logger.info("Startup completed — all pre-flight checks passed.")

    # Light mode: serve built frontend as static files (must be LAST)
    if settings.serve_frontend:
        from app.static_files import mount_frontend
        mount_frontend(application)

    return application


app = create_app()

# Combined ASGI app — Socket.IO handles /socket.io, FastAPI handles everything else
combined_app = socketio_lib.ASGIApp(sio, other_asgi_app=app)
