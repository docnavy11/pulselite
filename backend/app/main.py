from fastapi import FastAPI
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
    two_fa,
    webhooks,
    widget_config,
    workspaces,
)
from app.api.v1.public_chat import limiter
from app.config import settings


def create_app() -> FastAPI:
    application = FastAPI(title="Pulselite API", version="0.1.0", docs_url="/api/docs", redoc_url="/api/redoc")

    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
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

    # Public routes (no auth required)
    application.include_router(widget_config.router, prefix="/api/v1")
    application.include_router(public_chat.router, prefix="/api/v1")
    application.include_router(oauth.router, prefix="/api/v1")

    return application


app = create_app()
