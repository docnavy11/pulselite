from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import (
    actions,
    api_keys,
    articles,
    audit,
    auth,
    billing,
    chat,
    chatbots,
    completions,
    dashboard,
    documents,
    exceptions,
    gaps,
    gdpr,
    health,
    instagram,
    integrations,
    intelligence,
    invites,
    knowledge_bases,
    messenger,
    oauth,
    onboarding,
    public_chat,
    share,
    shopify_oauth,
    slack_events,
    sso,
    two_fa,
    webhooks,
    whatsapp,
    widget_config,
    workspaces,
)
from app.api.v1.public_chat import limiter
from app.config import settings


def create_app() -> FastAPI:
    application = FastAPI(title="Pulse API", version="0.1.0", docs_url="/api/docs", redoc_url="/api/redoc")

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
    application.include_router(audit.router, prefix="/api/v1")
    application.include_router(workspaces.router, prefix="/api/v1")
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(chatbots.router, prefix="/api/v1")
    application.include_router(knowledge_bases.router, prefix="/api/v1")
    application.include_router(documents.router, prefix="/api/v1")
    application.include_router(articles.router, prefix="/api/v1")
    application.include_router(chat.router, prefix="/api/v1")
    application.include_router(api_keys.router, prefix="/api/v1")
    application.include_router(completions.router, prefix="/api/v1")
    application.include_router(intelligence.router, prefix="/api/v1")
    application.include_router(gaps.router, prefix="/api/v1")
    application.include_router(exceptions.router, prefix="/api/v1")
    application.include_router(dashboard.router, prefix="/api/v1")
    application.include_router(integrations.router, prefix="/api/v1")
    application.include_router(billing.router, prefix="/api/v1")
    application.include_router(onboarding.router, prefix="/api/v1")
    application.include_router(gdpr.router, prefix="/api/v1")
    application.include_router(invites.router, prefix="/api/v1")
    application.include_router(actions.router, prefix="/api/v1")
    application.include_router(webhooks.router, prefix="/api/v1")
    application.include_router(sso.workspace_router, prefix="/api/v1")

    # Public routes (no auth required)
    application.include_router(widget_config.router, prefix="/api/v1")
    application.include_router(public_chat.router, prefix="/api/v1")
    application.include_router(share.router, prefix="/api/v1")
    application.include_router(oauth.router, prefix="/api/v1")
    application.include_router(slack_events.router, prefix="/api/v1")
    application.include_router(whatsapp.router, prefix="/api/v1")
    application.include_router(messenger.router, prefix="/api/v1")
    application.include_router(instagram.router, prefix="/api/v1")
    application.include_router(shopify_oauth.router, prefix="/api/v1")
    application.include_router(sso.auth_router, prefix="/api/v1")

    return application


app = create_app()
