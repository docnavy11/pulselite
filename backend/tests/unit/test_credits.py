"""Unit tests for app.services.credits — credit ledger operations."""
import pytest
from app.services.credits import (
    debit_credits,
    add_credits,
    get_balance,
    estimate_token_cost,
)


# ── estimate_token_cost (pure sync, no DB) ────────────────────────────────────

def test_estimate_token_cost_gpt4o_mini():
    cost = estimate_token_cost("gpt-4o-mini", 1000)
    assert cost == 1


def test_estimate_token_cost_gpt4o():
    cost = estimate_token_cost("gpt-4o", 1000)
    assert cost == 5


def test_estimate_token_cost_minimum_one():
    cost = estimate_token_cost("gpt-4o-mini", 1)
    assert cost >= 1


def test_estimate_token_cost_scales_with_tokens():
    cost_1k = estimate_token_cost("gpt-4o", 1000)
    cost_2k = estimate_token_cost("gpt-4o", 2000)
    assert cost_2k == cost_1k * 2


def test_estimate_token_cost_unknown_model_uses_default():
    # Unknown model should use default rate of 2 credits per 1k tokens
    cost = estimate_token_cost("unknown-model", 1000)
    assert cost == 2


def test_estimate_token_cost_zero_tokens_returns_minimum():
    cost = estimate_token_cost("gpt-4o", 0)
    assert cost >= 1


# ── DB operations ─────────────────────────────────────────────────────────────

async def test_get_balance_new_workspace(db, workspace):
    balance = await get_balance(db, workspace.id)
    assert isinstance(balance, int)
    assert balance >= 0


async def test_add_credits_increases_balance(db, workspace):
    before = await get_balance(db, workspace.id)
    new_balance = await add_credits(db, workspace.id, amount=100, reason="test_top_up")
    assert new_balance == before + 100


async def test_add_credits_returns_new_balance(db, workspace):
    before = await get_balance(db, workspace.id)
    result = await add_credits(db, workspace.id, amount=200, reason="test_return_value")
    assert result == before + 200


async def test_debit_credits_decreases_balance(db, workspace, mocker):
    # Mock Celery task dispatch to avoid real task queuing
    mocker.patch(
        "app.workers.tasks.auto_recharge.trigger_auto_recharge.delay",
        return_value=None,
    )
    await add_credits(db, workspace.id, amount=500, reason="test_setup")
    before = await get_balance(db, workspace.id)
    new_balance = await debit_credits(db, workspace.id, amount=50, reason="test_debit")
    assert new_balance == before - 50


async def test_debit_credits_insufficient_raises(db, workspace, mocker):
    mocker.patch(
        "app.workers.tasks.auto_recharge.trigger_auto_recharge.delay",
        return_value=None,
    )
    current = await get_balance(db, workspace.id)
    with pytest.raises(ValueError, match="Insufficient credit balance"):
        await debit_credits(db, workspace.id, amount=current + 99999, reason="test_overflow")


async def test_add_credits_creates_ledger_entry(db, workspace):
    from sqlalchemy import select
    from app.models.integrations import CreditLedger

    await add_credits(db, workspace.id, amount=250, reason="test_ledger_check")
    result = await db.execute(
        select(CreditLedger).where(
            CreditLedger.workspace_id == workspace.id,
            CreditLedger.reason == "test_ledger_check",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.amount == 250


async def test_debit_credits_creates_negative_ledger_entry(db, workspace, mocker):
    from sqlalchemy import select
    from app.models.integrations import CreditLedger

    mocker.patch(
        "app.workers.tasks.auto_recharge.trigger_auto_recharge.delay",
        return_value=None,
    )
    await add_credits(db, workspace.id, amount=500, reason="setup")
    await debit_credits(db, workspace.id, amount=75, reason="test_debit_ledger_check")
    result = await db.execute(
        select(CreditLedger).where(
            CreditLedger.workspace_id == workspace.id,
            CreditLedger.reason == "test_debit_ledger_check",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.amount == -75


async def test_ledger_entry_balance_after_is_correct(db, workspace):
    from sqlalchemy import select
    from app.models.integrations import CreditLedger

    await add_credits(db, workspace.id, amount=300, reason="test_balance_after")
    current = await get_balance(db, workspace.id)
    result = await db.execute(
        select(CreditLedger).where(
            CreditLedger.workspace_id == workspace.id,
            CreditLedger.reason == "test_balance_after",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.balance_after == current


async def test_get_balance_reflects_multiple_adds(db, workspace):
    before = await get_balance(db, workspace.id)
    await add_credits(db, workspace.id, amount=100, reason="add1")
    await add_credits(db, workspace.id, amount=200, reason="add2")
    after = await get_balance(db, workspace.id)
    assert after == before + 300


def test_estimate_token_cost_byok_applies_50_percent_discount():
    cost_full = estimate_token_cost("gpt-4o", 1000, is_byok=False)
    cost_byok = estimate_token_cost("gpt-4o", 1000, is_byok=True)
    assert cost_byok == max(1, cost_full // 2)


def test_estimate_token_cost_byok_minimum_one_credit():
    cost = estimate_token_cost("gpt-4o-mini", 1, is_byok=True)
    assert cost >= 1
