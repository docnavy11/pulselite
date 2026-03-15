import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.organizational import Workspace
from app.services.plan_service import get_plan_limits as _get_plan_limits

logger = logging.getLogger(__name__)

PLAN_PRICES = {
    "free": None,
    "starter": "price_starter",
    "growth": "price_growth",
    "professional": "price_professional",
    "agency": "price_agency",
    "enterprise": "price_enterprise",
}

PLAN_PRICES_ANNUAL = {
    "free": None,
    "starter": "price_starter_annual",
    "growth": "price_growth_annual",
    "professional": "price_professional_annual",
    "agency": "price_agency_annual",
    "enterprise": "price_enterprise_annual",
}


def get_stripe_client():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


async def create_checkout_session(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    plan: str,
    success_url: str,
    cancel_url: str,
    interval: str = "monthly",
) -> str:
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one()

    stripe = get_stripe_client()

    if not workspace.stripe_customer_id:
        customer = stripe.Customer.create(
            metadata={"workspace_id": str(workspace_id), "workspace_name": workspace.name}
        )
        workspace.stripe_customer_id = customer.id
        await db.flush()

    prices = PLAN_PRICES_ANNUAL if interval == "annual" else PLAN_PRICES
    price_id = prices.get(plan)
    if not price_id:
        raise ValueError(f"Invalid plan: {plan}")

    session = stripe.checkout.Session.create(
        customer=workspace.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"workspace_id": str(workspace_id), "plan": plan},
    )

    return session.url


async def create_portal_session(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    return_url: str,
) -> str:
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one()

    if not workspace.stripe_customer_id:
        raise ValueError("No Stripe customer for this workspace")

    stripe = get_stripe_client()
    session = stripe.billing_portal.Session.create(
        customer=workspace.stripe_customer_id,
        return_url=return_url,
    )
    return session.url


async def handle_webhook_event(db: AsyncSession, event: dict) -> None:
    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session_data = event["data"]["object"]
        workspace_id = session_data["metadata"].get("workspace_id")
        plan = session_data["metadata"].get("plan")
        subscription_id = session_data.get("subscription")

        if workspace_id and plan:
            result = await db.execute(select(Workspace).where(Workspace.id == uuid.UUID(workspace_id)))
            workspace = result.scalar_one_or_none()
            if workspace:
                workspace.plan = plan
                workspace.stripe_subscription_id = subscription_id
                limits = _get_plan_limits(plan)
                workspace.plan_conversation_cap = limits["conversations"]

    elif event_type == "customer.subscription.updated":
        subscription = event["data"]["object"]
        await _update_subscription(db, subscription)

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        result = await db.execute(select(Workspace).where(Workspace.stripe_customer_id == customer_id))
        workspace = result.scalar_one_or_none()
        if workspace:
            workspace.plan = "free"
            workspace.plan_conversation_cap = 100
            workspace.stripe_subscription_id = None


async def _update_subscription(db: AsyncSession, subscription: dict) -> None:
    customer_id = subscription.get("customer")
    result = await db.execute(select(Workspace).where(Workspace.stripe_customer_id == customer_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        return

    status = subscription.get("status")
    if status in ("active", "trialing"):
        price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
        for plan_map in (PLAN_PRICES, PLAN_PRICES_ANNUAL):
            for plan, pid in plan_map.items():
                if pid == price_id:
                    workspace.plan = plan
                    limits = _get_plan_limits(plan)
                    workspace.plan_conversation_cap = limits["conversations"]
                    break

