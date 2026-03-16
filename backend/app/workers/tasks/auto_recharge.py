import asyncio
import logging
import uuid
from datetime import datetime, timezone

import stripe

from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory, engine
from app.models.organizational import Workspace
from app.services import credits as credits_service
from app.services.realtime import emit_task_event
from app.services.deployment import is_self_hosted
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=55, time_limit=60)
def trigger_auto_recharge(self, workspace_id: str) -> dict:
    try:
        return asyncio.run(_recharge(uuid.UUID(workspace_id), self.request.id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _recharge(workspace_id: uuid.UUID, task_id: str) -> dict:
    if is_self_hosted():
        return {"status": "skipped", "detail": "Self-hosted mode"}
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            # Re-read workspace from committed DB state to guard against concurrent recharges
            # and pre-commit dispatch
            result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = result.scalar_one_or_none()
            if not workspace:
                return {"status": "error", "detail": "Workspace not found"}

            if not workspace.auto_recharge_enabled:
                return {"status": "skipped", "detail": "Auto-recharge disabled"}

            if not workspace.stripe_customer_id:
                return {"status": "error", "detail": "No Stripe customer"}

            if workspace.credit_balance > workspace.auto_recharge_threshold:
                return {"status": "skipped", "detail": "Balance already above threshold"}

            amount = workspace.auto_recharge_amount
            await emit_task_event(workspace_id, "started", "auto_recharge", task_id)

            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
                idempotency_key = f"recharge_{workspace_id}_{hour_key}"

                stripe.InvoiceItem.create(
                    customer=workspace.stripe_customer_id,
                    amount=int(amount * 0.04 * 100),  # $0.04/credit in cents
                    currency="usd",
                    description=f"Pulse credit top-up ({amount} credits)",
                    idempotency_key=idempotency_key,
                )
                invoice = stripe.Invoice.create(
                    customer=workspace.stripe_customer_id,
                    auto_advance=True,
                )
                invoice = stripe.Invoice.finalize_invoice(invoice.id)
                stripe.Invoice.pay(invoice.id)

            except Exception as e:
                logger.error(f"Stripe auto-recharge failed for {workspace_id}: {e}")
                raise

            new_balance = await credits_service.add_credits(
                session,
                workspace_id,
                amount,
                reason="auto_recharge",
            )
            await session.commit()

            logger.info(f"Auto-recharged {amount} credits for workspace {workspace_id}. New balance: {new_balance}")
            await emit_task_event(workspace_id, "completed", "auto_recharge", task_id, detail=f"Added {amount} credits")
            return {"status": "success", "credits_added": amount, "new_balance": new_balance}

        except Exception as e:
            await session.rollback()
            logger.error(f"Auto-recharge error: {e}")
            await emit_task_event(workspace_id, "completed", "auto_recharge", task_id, error=str(e))
            return {"status": "error", "detail": str(e)}
