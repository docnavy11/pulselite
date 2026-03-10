# Pulselite Simplification Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip enterprise features (SSO, ticketing, API keys, social channels, audit logs, white label, Shopify, lead scoring, BERTopic) from the Pulse codebase while keeping everything useful for SMB/indie customers.

**Architecture:** Delete self-contained files first, then trim mixed files (models, routes, tasks), then create a single Alembic migration to drop the removed DB tables/columns, then clean up frontend and infra. Each task leaves the codebase in a compilable state.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Next.js 15, Celery, Docker Compose

---

## What is REMOVED

| Area | Removed |
|---|---|
| Auth | SSO/OIDC, SSO config model |
| Ticketing | Exceptions router, Ticket model |
| API keys | api_keys router, ApiKey model, api_key_service |
| Audit | audit router, AuditLog model, audit service |
| Social channels | WhatsApp, Messenger, Instagram, Slack events routers |
| Shopify | shopify_oauth router |
| Actions | actions router, ChatbotAction/ActionEvent models, action_service |
| Share | share router (public conversation sharing) |
| Completions | completions router (multi-LLM endpoint, keep per-chatbot config) |
| Intelligence | Lead scoring (LeadScore, score_lead task), BERTopic (TopicCluster, cluster_topics/feature_requests tasks), IntelligenceSignal, AutonomousResolutionStats, geographic analytics, compute_daily_stats, send_alerts, auto_draft_article, log_retrieval tasks |
| White label | white_label_enabled field on Workspace; related endpoints |
| Intercom compat | intercom_app_id, intercom_id, intercom_part_id, intercom_ticket_id fields |
| Routing infra | Team, TeamMember, Inbox models; inbox_id/team_id/sla_policy_id on Conversation |
| Services | encryption (SSO-only), geoip, suggestion_service, web_search, action_service, audit service, api_key_service |
| Infra | k8s/ directory |

## What is KEPT

Intelligence (limited): GapEvent, GapCluster, ConversationAnalysis (sentiment + intent + topics + summary), RetrievalLog, cluster_gaps task, compute_sentiment_trends task, analyze_conversation task (trimmed)

---

## Task 1: Delete self-contained backend route files

**Files:**
- Delete: `backend/app/api/v1/sso.py`
- Delete: `backend/app/api/v1/exceptions.py`
- Delete: `backend/app/api/v1/api_keys.py`
- Delete: `backend/app/api/v1/audit.py`
- Delete: `backend/app/api/v1/instagram.py`
- Delete: `backend/app/api/v1/messenger.py`
- Delete: `backend/app/api/v1/whatsapp.py`
- Delete: `backend/app/api/v1/slack_events.py`
- Delete: `backend/app/api/v1/shopify_oauth.py`
- Delete: `backend/app/api/v1/actions.py`
- Delete: `backend/app/api/v1/share.py`
- Delete: `backend/app/api/v1/completions.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Delete the 12 route files**

```bash
cd /path/to/pulselite
rm backend/app/api/v1/sso.py
rm backend/app/api/v1/exceptions.py
rm backend/app/api/v1/api_keys.py
rm backend/app/api/v1/audit.py
rm backend/app/api/v1/instagram.py
rm backend/app/api/v1/messenger.py
rm backend/app/api/v1/whatsapp.py
rm backend/app/api/v1/slack_events.py
rm backend/app/api/v1/shopify_oauth.py
rm backend/app/api/v1/actions.py
rm backend/app/api/v1/share.py
rm backend/app/api/v1/completions.py
```

- [ ] **Step 2: Update main.py — remove all references to deleted routers**

Replace the entire `backend/app/main.py` with:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import (
    articles,
    auth,
    billing,
    chat,
    chatbots,
    dashboard,
    documents,
    gaps,
    gdpr,
    health,
    integrations,
    intelligence,
    invites,
    knowledge_bases,
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
    application.include_router(knowledge_bases.router, prefix="/api/v1")
    application.include_router(documents.router, prefix="/api/v1")
    application.include_router(articles.router, prefix="/api/v1")
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

    # Public routes (no auth required)
    application.include_router(widget_config.router, prefix="/api/v1")
    application.include_router(public_chat.router, prefix="/api/v1")
    application.include_router(oauth.router, prefix="/api/v1")

    return application


app = create_app()
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove SSO, ticketing, API keys, social channels, actions, share, completions routers"
```

---

## Task 2: Delete self-contained backend service files

**Files:**
- Delete: `backend/app/services/audit.py`
- Delete: `backend/app/services/api_key_service.py`
- Delete: `backend/app/services/action_service.py`
- Delete: `backend/app/services/geoip.py`
- Delete: `backend/app/services/suggestion_service.py`
- Delete: `backend/app/services/web_search.py`
- Delete: `backend/app/services/encryption.py`

- [ ] **Step 1: Delete service files**

```bash
rm backend/app/services/audit.py
rm backend/app/services/api_key_service.py
rm backend/app/services/action_service.py
rm backend/app/services/geoip.py
rm backend/app/services/suggestion_service.py
rm backend/app/services/web_search.py
rm backend/app/services/encryption.py
```

- [ ] **Step 2: Check no remaining imports of deleted services**

```bash
grep -r "from app.services.audit\|from app.services.api_key\|from app.services.action\|from app.services.geoip\|from app.services.suggestion\|from app.services.web_search\|from app.services.encryption" backend/app/ --include="*.py"
```

Fix any remaining imports found.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove audit, api_key, action, geoip, suggestion, web_search, encryption services"
```

---

## Task 3: Delete self-contained model files

**Files:**
- Delete: `backend/app/models/sso.py`
- Delete: `backend/app/models/audit.py`
- Delete: `backend/app/models/api_keys.py`
- Delete: `backend/app/models/actions.py`

- [ ] **Step 1: Delete model files**

```bash
rm backend/app/models/sso.py
rm backend/app/models/audit.py
rm backend/app/models/api_keys.py
rm backend/app/models/actions.py
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore: remove SSO, audit, api_keys, actions model files"
```

---

## Task 4: Trim organizational models

**Files:**
- Modify: `backend/app/models/organizational.py`

Remove: `Team`, `TeamMember`, `Inbox` classes entirely.
On `Workspace`: remove `white_label_enabled` and `intercom_app_id` fields.
On `Workspace`: remove `teams` and `inboxes` relationships.

- [ ] **Step 1: Rewrite organizational.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TimestampUpdateMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(Text, server_default=text("'free'"))
    plan_conversation_cap: Mapped[int] = mapped_column(Integer, server_default=text("100"))
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'UTC'"))
    primary_language: Mapped[str] = mapped_column(Text, server_default=text("'en'"))
    webhook_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    onboarding_step: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit_balance: Mapped[int] = mapped_column(Integer, server_default=text("1000"))
    auto_recharge_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    auto_recharge_threshold: Mapped[int] = mapped_column(Integer, server_default=text("200"))
    auto_recharge_amount: Mapped[int] = mapped_column(Integer, server_default=text("1000"))
    data_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    openrouter_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_models: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )

    agents: Mapped[list["Agent"]] = relationship(back_populates="workspace")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="workspace")


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("workspace_id", "email"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    two_fa_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="agents")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="agent")


class WorkspaceMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_memberships"

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'member'"))

    agent: Mapped["Agent"] = relationship(back_populates="memberships")
    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")


class WorkspaceWebhook(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workspace_webhooks"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    event_types: Mapped[list] = mapped_column(
        JSONB, server_default=text('\'["conversation.created", "conversation.escalated"]\'::jsonb'), nullable=False
    )
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
```

- [ ] **Step 2: Search for any remaining references to Team, TeamMember, Inbox**

```bash
grep -r "from app.models.organizational import.*Team\|from app.models.organizational import.*Inbox\|\.teams\|\.inboxes\|team_id\|inbox_id" backend/app/ --include="*.py" | grep -v "organizational.py"
```

Fix each occurrence found (nullify FK fields, remove references).

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove Team, TeamMember, Inbox models; drop white_label and intercom fields from Workspace"
```

---

## Task 5: Trim conversation models

**Files:**
- Modify: `backend/app/models/conversations.py`

Remove: `Ticket` class entirely.
From `Conversation`: remove `inbox_id`, `team_id`, `sla_policy_id`, `snoozed_until`, `waiting_since`, `intercom_id`, `external_id` fields. Keep `assignee_id` (can still manually assign). Keep `country_code`/`country_name` (still useful for basic geo display).
From `Message`: remove `intercom_part_id`.

- [ ] **Step 1: Edit conversations.py — remove Ticket class and trim Conversation/Message**

New `Conversation` class (replace in file):

```python
class Conversation(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "conversations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    priority: Mapped[str] = mapped_column(Text, server_default=text("'normal'"))
    channel: Mapped[str] = mapped_column(Text, server_default=text("'chat'"))
    lifecycle_stage: Mapped[str] = mapped_column(Text, server_default=text("'unknown'"))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_participated: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    autonomous_resolved: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stats: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")
    conversation_tags: Mapped[list["ConversationTag"]] = relationship(back_populates="conversation")
```

New `Message` class (remove `intercom_part_id`):

```python
class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    message_type: Mapped[str] = mapped_column(Text, nullable=False)
    author_type: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    part_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(Text, server_default=text("'text'"))
    attachments: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'sent'"))
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieval_log_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
```

Remove the `Ticket` class entirely (lines ~113–129 in original).

- [ ] **Step 2: Check for Ticket references elsewhere**

```bash
grep -r "from app.models.conversations import.*Ticket\|Ticket\b" backend/app/ --include="*.py" | grep -v "conversations.py"
```

Remove/fix any found.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove Ticket model, trim Conversation/Message Intercom/routing fields"
```

---

## Task 6: Trim intelligence models

**Files:**
- Modify: `backend/app/models/intelligence.py`

Remove: `LeadScore`, `TopicCluster`, `IntelligenceSignal`, `AutonomousResolutionStats` classes.
Trim `ConversationAnalysis`: remove `lead_intent`, `feature_requests`, `bug_reports`, `competitor_mentions`, `expansion_signals`, `churn_signals`, `customer_effort_score`, `action_items` fields.
Keep: `RetrievalLog`, `GapEvent`, `GapCluster`, `ConversationAnalysis` (slimmed).

- [ ] **Step 1: Rewrite intelligence.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RetrievalLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_logs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieved_chunk_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    reranked: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    escalated: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    response_generated: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    retrieval_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GapEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gap_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    retrieval_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retrieval_logs.id"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    gap_cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class GapCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gap_clusters"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=True)
    topic_label: Mapped[str] = mapped_column(Text, nullable=False)
    topic_keywords: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    gap_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    representative_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clustered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class ConversationAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_analysis"
    __table_args__ = (UniqueConstraint("conversation_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), unique=True, nullable=False
    )
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_primary: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_secondary: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    outcome_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str] = mapped_column(Text, server_default=text("'gpt-4o-mini'"))
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 2: Check for removed model references**

```bash
grep -r "LeadScore\|TopicCluster\|IntelligenceSignal\|AutonomousResolutionStats\|lead_intent\|feature_requests\|competitor_mentions\|expansion_signals\|churn_signals\|customer_effort_score" backend/app/ --include="*.py" | grep -v "intelligence.py\|alembic"
```

Fix/remove each occurrence found.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: trim intelligence models — remove LeadScore, TopicCluster, IntelligenceSignal, AutonomousResolutionStats; slim ConversationAnalysis"
```

---

## Task 7: Update models/__init__.py

**Files:**
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Rewrite __init__.py to only import surviving models**

```python
from app.models.organizational import Agent, Workspace, WorkspaceMembership, WorkspaceWebhook  # noqa: F401
from app.models.invites import WorkspaceInvite  # noqa: F401
from app.models.integrations import CreditLedger, IntegrationConfig  # noqa: F401
from app.models.contacts import Company, Contact, ContactEvent, DataAttribute, Segment  # noqa: F401
from app.models.conversations import Conversation, ConversationTag, Message, MessageFeedback, Tag  # noqa: F401
from app.models.knowledge import Article, ArticleCollection, Chatbot, Chunk, Document, KnowledgeBase  # noqa: F401
from app.models.intelligence import (  # noqa: F401
    ConversationAnalysis,
    GapCluster,
    GapEvent,
    RetrievalLog,
)

__all__ = [
    "Agent",
    "Article",
    "ArticleCollection",
    "Chatbot",
    "Chunk",
    "Company",
    "Contact",
    "ContactEvent",
    "Conversation",
    "ConversationAnalysis",
    "ConversationTag",
    "CreditLedger",
    "DataAttribute",
    "Document",
    "GapCluster",
    "GapEvent",
    "IntegrationConfig",
    "KnowledgeBase",
    "Message",
    "MessageFeedback",
    "RetrievalLog",
    "Segment",
    "Tag",
    "Workspace",
    "WorkspaceMembership",
    "WorkspaceInvite",
    "WorkspaceWebhook",
]
```

- [ ] **Step 2: Verify backend imports cleanly**

```bash
docker compose exec backend python -c "from app.models import *; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/__init__.py
git commit -m "chore: update models __init__ to reflect removed models"
```

---

## Task 8: Trim intelligence route

**Files:**
- Modify: `backend/app/api/v1/intelligence.py`

Keep: `get_retrieval_logs`, `get_gap_events`, `get_conversation_analysis`, `end_conversation` (remove `flush_lead_score` call), `get_sentiment_by_segment`.
Remove: `get_resolution_stats`, `get_lead_scores`, `get_intelligence_signals`, `get_chats_by_country`.

- [ ] **Step 1: Rewrite intelligence.py**

```python
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.contacts import Contact
from app.models.conversations import Conversation
from app.models.intelligence import ConversationAnalysis, GapEvent, RetrievalLog
from app.models.knowledge import Chatbot
from app.models.organizational import Agent
from app.schemas.intelligence import ConversationAnalysisResponse, GapEventResponse, RetrievalLogResponse
from app.services import conversation_service
from app.workers.tasks.analyze_conversation import analyze_conversation

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["intelligence"])


@router.get("/retrieval-logs", response_model=list[RetrievalLogResponse])
async def get_retrieval_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000_000),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RetrievalLog)
        .where(RetrievalLog.workspace_id == workspace_id)
        .order_by(RetrievalLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get("/gap-events", response_model=list[GapEventResponse])
async def get_gap_events(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000_000),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GapEvent)
        .where(GapEvent.workspace_id == workspace_id)
        .order_by(GapEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get("/conversations/{conversation_id}/analysis", response_model=ConversationAnalysisResponse)
async def get_conversation_analysis(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConversationAnalysis).where(
            ConversationAnalysis.conversation_id == conversation_id,
            ConversationAnalysis.workspace_id == workspace_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


@router.post("/conversations/{conversation_id}/end")
async def end_conversation(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await conversation_service.update_conversation_status(db, conversation_id, "resolved")
    analyze_conversation.delay(str(conversation_id), str(workspace_id))
    return {"status": "resolved", "conversation_id": str(conversation_id)}


@router.get("/sentiment-by-segment")
async def get_sentiment_by_segment(
    workspace_id: uuid.UUID = Depends(get_workspace),
    days: int = Query(30, ge=1, le=90),
    segment: str = Query("chatbot"),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if segment == "chatbot":
        result = await db.execute(
            select(
                Chatbot.name,
                func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
                func.count().label("count"),
            )
            .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            .join(Chatbot, Chatbot.id == Conversation.chatbot_id)
            .where(
                ConversationAnalysis.workspace_id == workspace_id,
                ConversationAnalysis.sentiment_score.isnot(None),
                ConversationAnalysis.created_at >= cutoff,
            )
            .group_by(Chatbot.id, Chatbot.name)
            .order_by(func.count().desc())
        )
    else:
        result = await db.execute(
            select(
                func.coalesce(Contact.name, Contact.email, "Anonymous").label("name"),
                func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
                func.count().label("count"),
            )
            .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            .join(Contact, Contact.id == Conversation.contact_id)
            .where(
                ConversationAnalysis.workspace_id == workspace_id,
                ConversationAnalysis.sentiment_score.isnot(None),
                ConversationAnalysis.created_at >= cutoff,
            )
            .group_by(Contact.id, Contact.name, Contact.email)
            .order_by(func.count().desc())
            .limit(10)
        )

    rows = result.all()
    data = [
        {"name": row.name, "avg_sentiment": round(float(row.avg_sentiment), 3), "count": row.count}
        for row in rows
    ]
    return {"data": data}
```

- [ ] **Step 2: Trim intelligence schemas to match**

Check `backend/app/schemas/intelligence.py`. Remove schemas for `LeadScoreResponse`, `IntelligenceSignalResponse`, `ResolutionStatsResponse`. Keep `ConversationAnalysisResponse` (update fields to match trimmed model), `GapEventResponse`, `RetrievalLogResponse`.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: trim intelligence route — remove lead scores, signals, resolution stats, geo endpoints"
```

---

## Task 9: Trim workspaces route — remove white label

**Files:**
- Modify: `backend/app/api/v1/workspaces.py`
- Modify: `backend/app/schemas/workspaces.py`

- [ ] **Step 1: Search for white_label references in workspaces route**

```bash
grep -n "white_label" backend/app/api/v1/workspaces.py backend/app/schemas/workspaces.py backend/app/services/workspace_service.py
```

- [ ] **Step 2: Remove white_label endpoints and schema fields**

In `workspaces.py`: delete any endpoint like `PUT /white-label` or field setting `white_label_enabled`.
In schemas: remove `white_label_enabled` from any workspace response/request schema.
In `workspace_service.py`: remove any white label logic.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove white label from workspaces route and schemas"
```

---

## Task 10: Trim analyze_conversation Celery task

**Files:**
- Modify: `backend/app/workers/tasks/analyze_conversation.py`

Remove: `_fan_out_signals` function and all its calls (removes `IntelligenceSignal` dependency).
Trim: LLM prompt to only request `sentiment_score`, `sentiment_label`, `intent_primary`, `intent_secondary`, `outcome_category`, `topics`, `summary`.
Trim: `ConversationAnalysis` fields written to match slimmed model.

- [ ] **Step 1: Rewrite analyze_conversation.py**

```python
import asyncio
import json
import logging
import time
import uuid

from openai import AsyncOpenAI
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.conversations import Message
from app.models.intelligence import ConversationAnalysis
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Analyze this customer support conversation and extract structured data.
Return a JSON object with exactly these fields:

{
  "sentiment_score": float (-1.0 to 1.0),
  "sentiment_label": "positive" | "neutral" | "negative" | "mixed",
  "intent_primary": string (main intent of the conversation),
  "intent_secondary": string[] (secondary intents),
  "outcome_category": "resolved" | "unresolved" | "escalated" | "abandoned",
  "topics": string[] (main topics discussed),
  "summary": string (2-sentence summary)
}

Conversation transcript:
"""


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def analyze_conversation(self, conversation_id: str, workspace_id: str) -> dict:
    try:
        return asyncio.run(_analyze(uuid.UUID(conversation_id), uuid.UUID(workspace_id)))
    except Exception as exc:
        self.retry(exc=exc)


async def _analyze(conversation_id: uuid.UUID, workspace_id: uuid.UUID) -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
            )
            messages = result.scalars().all()

            if not messages:
                return {"status": "skipped", "reason": "no messages"}

            transcript = _build_transcript(messages)
            start_time = time.monotonic()
            analysis_data = await _call_llm(transcript)

            analysis = ConversationAnalysis(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                sentiment_score=analysis_data.get("sentiment_score"),
                sentiment_label=analysis_data.get("sentiment_label"),
                intent_primary=analysis_data.get("intent_primary"),
                intent_secondary=analysis_data.get("intent_secondary"),
                outcome_category=analysis_data.get("outcome_category"),
                topics=analysis_data.get("topics"),
                summary=analysis_data.get("summary"),
                processing_ms=int((time.monotonic() - start_time) * 1000),
            )
            session.add(analysis)
            await session.commit()
            return {"status": "success", "conversation_id": str(conversation_id)}
        except Exception:
            await session.rollback()
            raise


def _build_transcript(messages: list[Message]) -> str:
    lines = []
    for msg in messages:
        role = msg.author_type.upper()
        content = msg.content or "[no content]"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def _call_llm(transcript: str) -> dict:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert conversation analyst. Always respond with valid JSON."},
            {"role": "user", "content": ANALYSIS_PROMPT + transcript},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=500,
    )
    return json.loads(response.choices[0].message.content)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/workers/tasks/analyze_conversation.py
git commit -m "chore: trim analyze_conversation — remove signal fan-out, slim LLM prompt to sentiment+intent+topics"
```

---

## Task 11: Delete Celery tasks

**Files:**
- Delete: `backend/app/workers/tasks/score_lead.py`
- Delete: `backend/app/workers/tasks/cluster_topics.py`
- Delete: `backend/app/workers/tasks/cluster_feature_requests.py`
- Delete: `backend/app/workers/tasks/compute_daily_stats.py`
- Delete: `backend/app/workers/tasks/send_alerts.py`
- Delete: `backend/app/workers/tasks/auto_draft_article.py`
- Delete: `backend/app/workers/tasks/log_retrieval.py`
- Modify: `backend/app/workers/tasks/__init__.py` (remove deleted task imports)
- Check: Celery Beat schedule in `backend/app/workers/celery_app.py`

- [ ] **Step 1: Delete task files**

```bash
rm backend/app/workers/tasks/score_lead.py
rm backend/app/workers/tasks/cluster_topics.py
rm backend/app/workers/tasks/cluster_feature_requests.py
rm backend/app/workers/tasks/compute_daily_stats.py
rm backend/app/workers/tasks/send_alerts.py
rm backend/app/workers/tasks/auto_draft_article.py
rm backend/app/workers/tasks/log_retrieval.py
```

- [ ] **Step 2: Update tasks/__init__.py and celery_app.py**

```bash
# Check what imports the removed tasks
grep -r "score_lead\|cluster_topics\|cluster_feature\|compute_daily\|send_alerts\|auto_draft\|log_retrieval" backend/app/ --include="*.py"
```

Remove all found references from `__init__.py` and the Celery Beat schedule.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove lead scoring, BERTopic, daily stats, alerts, auto-draft, log_retrieval Celery tasks"
```

---

## Task 12: Delete outdated tests

**Files:**
- Delete: `backend/tests/unit/test_api_key_service.py`
- Delete: `backend/tests/unit/test_lead_scoring.py`
- Delete: `backend/tests/unit/test_encryption.py`
- Delete: `backend/tests/integration/test_exceptions_api.py`

- [ ] **Step 1: Delete test files**

```bash
rm backend/tests/unit/test_api_key_service.py
rm backend/tests/unit/test_lead_scoring.py
rm backend/tests/unit/test_encryption.py
rm backend/tests/integration/test_exceptions_api.py
```

- [ ] **Step 2: Scan remaining tests for removed model/service imports**

```bash
grep -r "ApiKey\|LeadScore\|Ticket\|AuditLog\|SSOConfig\|IntelligenceSignal\|TopicCluster\|AutonomousResolutionStats\|Team\b\|Inbox\b" backend/tests/ --include="*.py"
```

Fix each found reference (remove the test or update the fixture).

- [ ] **Step 3: Run remaining tests to get a baseline**

```bash
docker compose exec backend pytest tests/unit/ -v 2>&1 | tail -30
```

Note how many pass/fail. Some will fail due to removed schema fields — fix them in subsequent steps.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove tests for deleted features (api_keys, lead_scoring, encryption, exceptions)"
```

---

## Task 13: Write Alembic migration to drop removed tables and columns

**Files:**
- Create: `backend/alembic/versions/2026_03_10_drop_enterprise_features.py`

This migration drops tables and columns for everything removed. It must be written as a proper Alembic migration with `upgrade()` and `downgrade()`.

- [ ] **Step 1: Create migration file**

```bash
docker compose exec backend alembic revision --autogenerate -m "drop_enterprise_features"
```

If autogenerate doesn't catch everything (it may not for column removals), manually write the migration:

```python
"""drop enterprise features

Revision ID: drop_enterprise_features
Revises: <latest_revision_id>
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa

revision = 'drop_enterprise_features'
down_revision = '<latest_revision_id>'  # replace with actual
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop enterprise tables (CASCADE handles FKs)
    op.drop_table('tickets')
    op.drop_table('api_keys')
    op.drop_table('audit_logs')
    op.drop_table('teams')          # team_members FK cascades
    op.drop_table('team_members')
    op.drop_table('inboxes')
    op.drop_table('intelligence_signals')
    op.drop_table('lead_scores')
    op.drop_table('topic_clusters')
    op.drop_table('autonomous_resolution_stats')
    op.drop_table('sso_configs')

    # Drop columns from workspaces
    op.drop_column('workspaces', 'white_label_enabled')
    op.drop_column('workspaces', 'intercom_app_id')

    # Drop columns from conversations
    op.drop_column('conversations', 'inbox_id')
    op.drop_column('conversations', 'team_id')
    op.drop_column('conversations', 'sla_policy_id')
    op.drop_column('conversations', 'snoozed_until')
    op.drop_column('conversations', 'waiting_since')
    op.drop_column('conversations', 'intercom_id')
    op.drop_column('conversations', 'external_id')

    # Drop columns from messages
    op.drop_column('messages', 'intercom_part_id')

    # Drop columns from conversation_analysis
    op.drop_column('conversation_analysis', 'lead_intent')
    op.drop_column('conversation_analysis', 'feature_requests')
    op.drop_column('conversation_analysis', 'bug_reports')
    op.drop_column('conversation_analysis', 'competitor_mentions')
    op.drop_column('conversation_analysis', 'expansion_signals')
    op.drop_column('conversation_analysis', 'churn_signals')
    op.drop_column('conversation_analysis', 'customer_effort_score')
    op.drop_column('conversation_analysis', 'action_items')

    # Drop columns from agents
    op.drop_column('agents', 'has_inbox_seat')
    op.drop_column('agents', 'availability')

    # Drop gap_clusters.draft_article_id FK (no more auto-draft)
    op.drop_column('gap_clusters', 'draft_article_id')
    op.drop_column('gap_clusters', 'resolution_impact')

    # Drop retrieval_logs.query_embedding_model (cleanup)
    op.drop_column('retrieval_logs', 'query_embedding_model')


def downgrade() -> None:
    # Downgrade not supported for this destructive migration
    raise NotImplementedError("Downgrade not supported")
```

- [ ] **Step 2: Verify which tables/columns actually exist before running**

```bash
docker compose exec backend python -c "
from app.database import engine
import asyncio
from sqlalchemy import inspect, text
async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name\"))
        print([r[0] for r in result])
asyncio.run(check())
"
```

Adjust migration to only drop tables that actually exist.

- [ ] **Step 3: Run migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected: Migration completes without errors.

- [ ] **Step 4: Verify backend starts cleanly**

```bash
docker compose restart backend
docker compose exec backend python -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: Alembic migration — drop enterprise tables and columns"
```

---

## Task 14: Delete frontend pages

**Files:**
- Delete: `frontend/src/app/(auth)/sso/` (directory)
- Delete: `frontend/src/app/(dashboard)/settings/sso/`
- Delete: `frontend/src/app/(dashboard)/settings/audit-logs/`
- Delete: `frontend/src/app/(dashboard)/exceptions/` (directory)
- Delete: `frontend/src/app/(dashboard)/intelligence/leads/` (directory)
- Delete: `frontend/src/app/(dashboard)/intelligence/geography/`
- Delete: `frontend/src/app/(dashboard)/intelligence/competitive/`
- Delete: `frontend/src/app/(dashboard)/intelligence/features/`
- Delete: `frontend/src/app/(dashboard)/chatbots/[id]/actions/`

- [ ] **Step 1: Delete page directories**

```bash
rm -rf frontend/src/app/(auth)/sso
rm -rf frontend/src/app/(dashboard)/settings/sso
rm -rf frontend/src/app/(dashboard)/settings/audit-logs
rm -rf frontend/src/app/(dashboard)/exceptions
rm -rf frontend/src/app/(dashboard)/intelligence/leads
rm -rf frontend/src/app/(dashboard)/intelligence/geography
rm -rf frontend/src/app/(dashboard)/intelligence/competitive
rm -rf frontend/src/app/(dashboard)/intelligence/features
rm -rf frontend/src/app/(dashboard)/chatbots/\[id\]/actions
```

- [ ] **Step 2: Remove API keys section from settings/security page**

Edit `frontend/src/app/(dashboard)/settings/security/page.tsx`: remove the API keys UI section (keep 2FA section).

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove SSO, audit-logs, exceptions, leads, geo, competitive, features, actions frontend pages"
```

---

## Task 15: Update frontend Sidebar navigation

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

Remove navigation links for deleted pages. Keep: dashboard, chatbots, conversations, intelligence (gaps + sentiment + topics), settings (team, billing, integrations, llm, security/2FA, data-retention, webhooks).

- [ ] **Step 1: Read and edit Sidebar.tsx**

Search for and remove links to:
- `/exceptions`
- `/settings/sso`
- `/settings/audit-logs`
- `/intelligence/leads`
- `/intelligence/geography`
- `/intelligence/competitive`
- `/intelligence/features`

```bash
grep -n "exceptions\|audit-logs\|/sso\|intelligence/leads\|geography\|competitive\|intelligence/features" frontend/src/components/layout/Sidebar.tsx
```

Remove each found navigation entry.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx
git commit -m "chore: remove deleted page links from Sidebar navigation"
```

---

## Task 16: Clean up frontend API functions and types

**Files:**
- Modify: `frontend/src/lib/api-functions.ts`
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Remove API functions for deleted features**

```bash
grep -n "exception\|apiKey\|auditLog\|sso\|leadScore\|intelligenceSignal\|resolutionStats\|whiteLab\|shopify\|whatsapp\|messenger\|instagram\|slack" frontend/src/lib/api-functions.ts | head -40
```

Remove all functions related to: exceptions/tickets, API keys, audit logs, SSO, lead scores, intelligence signals, resolution stats, white label, Shopify, WhatsApp, Messenger, Instagram, Slack events.

- [ ] **Step 2: Remove types for deleted features**

```bash
grep -n "Exception\|ApiKey\|AuditLog\|SSOConfig\|LeadScore\|IntelligenceSignal\|ResolutionStats\|WhiteLabel\|Ticket\b" frontend/src/lib/types.ts
```

Remove each found type definition.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api-functions.ts frontend/src/lib/types.ts
git commit -m "chore: remove deleted feature API functions and TypeScript types"
```

---

## Task 17: Delete Kubernetes infra

**Files:**
- Delete: `infra/k8s/` (entire directory)

- [ ] **Step 1: Delete k8s directory**

```bash
rm -rf infra/k8s
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore: remove Kubernetes infra — not needed for Pulselite"
```

---

## Task 18: Final verification

- [ ] **Step 1: Build and start backend cleanly**

```bash
docker compose up -d --build
sleep 10
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
```

Expected: `{"status": "ok"}` or similar.

- [ ] **Step 2: Run backend tests**

```bash
docker compose exec backend pytest tests/unit/ tests/integration/ -v --tb=short 2>&1 | tail -50
```

Fix any remaining failures caused by removed features.

- [ ] **Step 3: Run frontend build**

```bash
docker compose exec frontend npm run build 2>&1 | tail -30
```

Fix any TypeScript errors from removed types/functions.

- [ ] **Step 4: Run frontend unit tests**

```bash
docker compose exec frontend npm test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: pulselite simplification complete — enterprise features removed"
```

---

## Summary of changes

| Area | Before | After |
|---|---|---|
| Backend routes | 26 routers | 18 routers |
| DB tables | ~41 | ~28 |
| Celery tasks | 18 | 11 |
| Frontend pages | ~40 | ~28 |
| Models | 41 classes | ~28 classes |
