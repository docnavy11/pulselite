import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent, Workspace
from app.services import billing as billing_service
from app.services import credits as credits_service

MODEL_COSTS: dict[str, float] = {
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.001,
    "gpt-3.5-turbo": 0.0005,
    "claude-opus-4-6": 0.015,
    "claude-sonnet-4-6": 0.003,
    "claude-haiku-4-5": 0.00025,
    "gemini-1.5-pro": 0.0035,
    "gemini-1.5-flash": 0.000075,
}
DEFAULT_COST_PER_1K = 0.001

router = APIRouter(tags=["billing"])


def _validate_return_url(url: str | None) -> None:
    if url and not url.startswith(settings.FRONTEND_URL):
        raise HTTPException(status_code=400, detail="Invalid return URL")

def _build_billing_plans() -> list[dict]:
    """Build billing plans response from cached plan tiers."""
    from app.services.plan_service import get_all_tiers

    display_order = ["free", "starter", "growth", "agency", "enterprise"]
    all_tiers = {t.slug: t for t in get_all_tiers()}
    plans = []
    for slug in display_order:
        tier = all_tiers.get(slug)
        if tier is None:
            continue
        plans.append({
            "id": tier.slug,
            "name": tier.name,
            "price": tier.price_monthly_cents / 100,
            "features": tier.features,
            "limits": {
                "chatbots": tier.max_chatbots,
                "conversations": tier.max_conversations_monthly,
                "knowledge_bases": tier.max_knowledge_bases,
                "chars_indexed": tier.max_chars_indexed,
            },
        })
    return plans


@router.get("/workspaces/{workspace_id}/billing/usage")
async def get_usage_breakdown(
    workspace_id: uuid.UUID = Depends(get_workspace),
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    """Return token usage and cost breakdown for the workspace over the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    from sqlalchemy import text as sa_text

    raw = await db.execute(
        sa_text(
            """
            SELECT
                m.content,
                m.created_at::date AS day,
                c.llm_model,
                c.llm_provider
            FROM messages m
            JOIN conversations conv ON conv.id = m.conversation_id
            JOIN chatbots c ON c.id = conv.chatbot_id
            WHERE m.workspace_id = :workspace_id
              AND m.author_type = 'bot'
              AND m.created_at >= :since
            """
        ),
        {"workspace_id": str(workspace_id), "since": since},
    )
    rows = raw.fetchall()

    # Aggregate by model
    model_tokens: dict[str, int] = {}
    model_provider: dict[str, str] = {}
    daily_tokens: dict[str, int] = {}

    for content, day, llm_model, llm_provider in rows:
        # Estimate tokens: ~4 chars per token (rough approximation)
        chars = len(content or "")
        tokens = max(1, chars // 4)

        model_key = llm_model or "gpt-4o-mini"
        provider_key = llm_provider or "openai"
        day_str = str(day)

        model_tokens[model_key] = model_tokens.get(model_key, 0) + tokens
        if model_key not in model_provider:
            model_provider[model_key] = provider_key
        daily_tokens[day_str] = daily_tokens.get(day_str, 0) + tokens

    total_tokens = sum(model_tokens.values())

    # Build breakdown
    breakdown = []
    total_cost = 0.0
    for model, tokens in model_tokens.items():
        cost_per_1k = MODEL_COSTS.get(model, DEFAULT_COST_PER_1K)
        cost = (tokens / 1000) * cost_per_1k
        total_cost += cost
        breakdown.append(
            {
                "model": model,
                "provider": model_provider.get(model, "openai"),
                "tokens": tokens,
                "cost_usd": round(cost, 6),
            }
        )

    # Build daily series (fill gaps with 0)
    daily = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
        day_str = str(d)
        t = daily_tokens.get(day_str, 0)
        cost_per_1k = DEFAULT_COST_PER_1K  # approximate for daily
        daily.append(
            {
                "date": day_str,
                "tokens": t,
                "cost_usd": round((t / 1000) * cost_per_1k, 6),
            }
        )

    return {
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "breakdown": breakdown,
        "daily": daily,
    }


@router.get("/billing/plans")
async def get_billing_plans():
    return _build_billing_plans()


class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str
    interval: str = "monthly"


class PortalRequest(BaseModel):
    return_url: str


@router.post("/workspaces/{workspace_id}/billing/checkout")
async def create_checkout(
    body: CheckoutRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    _validate_return_url(body.success_url)
    _validate_return_url(body.cancel_url)
    try:
        url = await billing_service.create_checkout_session(
            db, workspace_id, body.plan, body.success_url, body.cancel_url, body.interval
        )
        return {"url": url}
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/workspaces/{workspace_id}/billing/portal")
async def create_portal(
    body: PortalRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    _validate_return_url(body.return_url)
    try:
        url = await billing_service.create_portal_session(db, workspace_id, body.return_url)
        return {"url": url}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/billing/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    import stripe

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    await billing_service.handle_webhook_event(db, event)
    return {"status": "ok"}


@router.get("/workspaces/{workspace_id}/credits/balance")
async def get_credit_balance(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    from datetime import datetime, timezone
    from sqlalchemy import func as sqlfunc
    from app.models.integrations import CreditLedger

    balance = await credits_service.get_balance(db, workspace_id)

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used_result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(-CreditLedger.amount), 0)).where(
            CreditLedger.workspace_id == workspace_id,
            CreditLedger.amount < 0,
            CreditLedger.created_at >= month_start,
        )
    )
    used_this_month = int(used_result.scalar() or 0)

    return {"balance": balance, "used_this_month": used_this_month}


@router.get("/workspaces/{workspace_id}/credits/history")
async def get_credit_history(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000_000),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    entries = await credits_service.get_history(db, workspace_id, limit, offset)
    return [
        {
            "id": str(e.id),
            "amount": e.amount,
            "reason": e.reason,
            "reference_id": e.reference_id,
            "balance_after": e.balance_after,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


class AutoRechargeSettings(BaseModel):
    auto_recharge_enabled: bool
    auto_recharge_threshold: int = Field(ge=0, le=1_000_000)
    auto_recharge_amount: int = Field(ge=0, le=1_000_000)


@router.get("/workspaces/{workspace_id}/billing/auto-recharge")
async def get_auto_recharge(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(
            Workspace.auto_recharge_enabled,
            Workspace.auto_recharge_threshold,
            Workspace.auto_recharge_amount,
        ).where(Workspace.id == workspace_id)
    )
    row = result.one()
    return {
        "auto_recharge_enabled": row[0],
        "auto_recharge_threshold": row[1],
        "auto_recharge_amount": row[2],
    }


@router.put("/workspaces/{workspace_id}/billing/auto-recharge")
async def update_auto_recharge(
    body: AutoRechargeSettings,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    await db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(
            auto_recharge_enabled=body.auto_recharge_enabled,
            auto_recharge_threshold=body.auto_recharge_threshold,
            auto_recharge_amount=body.auto_recharge_amount,
        )
    )
    await db.commit()
    return {"status": "ok"}
