"""Credit system — no Redis dependency."""

import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import CreditLedger
from app.models.organizational import Workspace

logger = logging.getLogger(__name__)

COST_PER_1K_TOKENS = {
    "gpt-4o-mini": 1,
    "gpt-4o": 5,
    "gpt-4": 10,
    "claude-sonnet-4-6": 3,
    "claude-opus-4-6": 15,
    "claude-haiku-4-5-20251001": 1,
    "gemini-2.0-flash": 1,
}


async def debit_credits(
    db: AsyncSession, workspace_id: uuid.UUID, amount: int, reason: str, reference_id: str | None = None
) -> int:
    result = await db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id, Workspace.credit_balance >= amount)
        .values(credit_balance=Workspace.credit_balance - amount)
        .returning(Workspace.credit_balance, Workspace.auto_recharge_enabled, Workspace.auto_recharge_threshold)
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError("Insufficient credit balance")
    new_balance = row[0]
    ledger_entry = CreditLedger(
        workspace_id=workspace_id, amount=-amount, reason=reason, reference_id=reference_id, balance_after=new_balance
    )
    db.add(ledger_entry)
    await db.flush()
    return new_balance


async def add_credits(
    db: AsyncSession, workspace_id: uuid.UUID, amount: int, reason: str, reference_id: str | None = None
) -> int:
    result = await db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(credit_balance=Workspace.credit_balance + amount)
        .returning(Workspace.credit_balance)
    )
    new_balance = result.scalar_one()
    ledger_entry = CreditLedger(
        workspace_id=workspace_id, amount=amount, reason=reason, reference_id=reference_id, balance_after=new_balance
    )
    db.add(ledger_entry)
    await db.flush()
    return new_balance


async def get_balance(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    result = await db.execute(select(Workspace.credit_balance).where(Workspace.id == workspace_id))
    return result.scalar() or 0


async def get_history(
    db: AsyncSession, workspace_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> list[CreditLedger]:
    result = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.workspace_id == workspace_id)
        .order_by(CreditLedger.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


def estimate_token_cost(model: str, token_count: int, is_byok: bool = False) -> int:
    rate = COST_PER_1K_TOKENS.get(model, 2)
    cost = max(1, (token_count * rate) // 1000)
    if is_byok:
        cost = max(1, cost // 2)
    return cost
