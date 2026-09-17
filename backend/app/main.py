"""PulseLight v2 — FastAPI app with Jinja2 + HTMX, no React/Celery/Redis."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import settings
from app.database import get_db, async_session_factory
from app.models.organizational import Agent, Workspace, WorkspaceMembership
from app.models.session import Session

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    app.state._start_time = datetime.now(timezone.utc)
    # Preload embedding model BEFORE wiring LogBuffer — PyTorch/OMP thread spawning
    # deadlocks if LogBuffer's threading.Lock is held on the app.* logger during model load.
    try:
        from app.services.ingestion.embedder import _get_model
        _get_model()
        logger.info("Embedding model preloaded")
    except Exception:
        logger.warning("Failed to preload embedding model", exc_info=True)
    # Wire in-memory log buffer AFTER model load (app.* only, NOT root logger)
    from app.services.log_buffer import LogBuffer as _LogBuffer
    _log_buffer = _LogBuffer.get_instance()
    _log_buffer.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("app").addHandler(_log_buffer)

    # Bootstrap admin user
    try:
        from app.services.bootstrap import bootstrap_admin
        await bootstrap_admin()
    except Exception:
        logger.warning("Admin bootstrap failed", exc_info=True)

    # Start background job worker
    from app.background.runner import start_worker, stop_worker
    start_worker()

    # Start scheduler
    from app.background.scheduler import setup_scheduler
    setup_scheduler()

    # Register job handlers (import triggers @register_job decorators)
    import app.background.jobs  # noqa: F401

    logger.info("PulseLight v2 started")
    yield

    # Shutdown
    stop_worker()
    from app.background.scheduler import scheduler
    scheduler.shutdown(wait=False)
    logger.info("PulseLight v2 stopped")


app = FastAPI(title="PulseLight", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)

# Templates
templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# CORS (for widget script on external sites)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Session middleware ---

# Public paths that don't require authentication
_PUBLIC_PATHS = {
    "/login", "/register", "/auth/google", "/auth/google/callback",
    "/api/health", "/api/config/deployment", "/api/chat", "/api/widget",
    "/static", "/favicon.ico",
}


def _is_public(path: str) -> bool:
    for public in _PUBLIC_PATHS:
        if path.startswith(public):
            return True
    return False


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    """Load user and workspace from session cookie. Redirect to /login if not authenticated."""
    request.state.user = None
    request.state.workspace = None
    request.state.workspaces = []

    if _is_public(request.url.path):
        return await call_next(request)

    session_id = request.cookies.get("session_id")
    if not session_id:
        if request.headers.get("HX-Request"):
            from starlette.responses import Response
            response = Response(status_code=401)
            response.headers["HX-Redirect"] = "/login"
            return response
        return RedirectResponse("/login")

    async with async_session_factory() as db:
        from datetime import datetime, timezone
        session_result = await db.execute(
            select(Session).where(Session.id == session_id, Session.expires_at > datetime.now(timezone.utc))
        )
        session = session_result.scalar_one_or_none()
        if not session:
            response = RedirectResponse("/login")
            response.delete_cookie("session_id")
            return response

        user_result = await db.execute(select(Agent).where(Agent.id == session.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            response = RedirectResponse("/login")
            response.delete_cookie("session_id")
            return response

        workspace_result = await db.execute(select(Workspace).where(Workspace.id == session.workspace_id))
        workspace = workspace_result.scalar_one_or_none()

        request.state.user = user
        request.state.workspace = workspace

        # Load all workspaces the user is a member of (for switcher)
        memberships_result = await db.execute(
            select(WorkspaceMembership, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(WorkspaceMembership.agent_id == user.id)
            .order_by(Workspace.name)
        )
        request.state.workspaces = [ws for _, ws in memberships_result.all()]

    return await call_next(request)


# --- Security headers ---

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# --- Register routers ---

from app.routes.auth import router as auth_router
from app.routes.chatbots import router as chatbots_router
from app.routes.conversations import router as conversations_router
from app.routes.dashboard import router as dashboard_router
from app.routes.api import router as api_router
from app.routes.events import router as events_router
from app.routes.settings import router as settings_router
from app.routes.qa import router as qa_router
from app.routes.actions import router as actions_router
from app.routes.crawl import router as crawl_router
from app.routes.documents import router as documents_router
from app.routes.intelligence import router as intelligence_router
from app.routes.logs import router as logs_router
from app.routes.articles import router as articles_router
from app.routes.audit import router as audit_router
from app.routes.admin import router as admin_router
from app.routes.search import router as search_router

app.include_router(auth_router)
app.include_router(chatbots_router)
app.include_router(conversations_router)
app.include_router(dashboard_router)
app.include_router(api_router)
app.include_router(events_router)
app.include_router(settings_router)
app.include_router(qa_router)
app.include_router(actions_router)
app.include_router(crawl_router)
app.include_router(documents_router)
app.include_router(intelligence_router)
app.include_router(logs_router)
app.include_router(articles_router)
app.include_router(audit_router)
app.include_router(admin_router)
app.include_router(search_router)
