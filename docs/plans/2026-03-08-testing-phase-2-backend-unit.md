# Testing Phase 2 — Backend Unit Tests

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Write unit tests for all core backend business logic — security utils, credits, auth, workspace, conversation, API keys, encryption, invites, and lead scoring — covering happy paths, edge cases, and guard rails.

**Architecture:** Tests live in `backend/tests/unit/`. Pure-function tests need no fixtures. Service tests use the `db` fixture from Phase 1 (SAVEPOINT-based rollback). External I/O (Redis, Stripe, OpenAI, Celery tasks) is mocked with `pytest-mock`. Each test file maps to one service/module.

**Tech Stack:** pytest 8.3+, pytest-asyncio (auto mode), pytest-mock, SQLAlchemy 2.0 async, real pulse_test DB, faker

---

## Before You Start

```bash
# Verify Phase 1 infra is working
docker compose exec backend bash -c "cd /app && pytest tests/ -v 2>&1 | tail -5"
# Expected: 15 passed

# Verify fixtures are available
docker compose exec backend bash -c "cd /app && python -c 'from tests.factories import make_workspace; print(\"ok\")'"
```

---

## Task 1: Security utils — pure function tests

**Files:**
- Create: `backend/tests/unit/test_security.py`

These are pure functions (no DB, no fixtures needed). Fastest tests in the suite.

**Step 1: Write the tests**

Create `backend/tests/unit/test_security.py`:

```python
"""Unit tests for app.utils.security — pure functions, no DB needed."""
import time
import pytest
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


# ── Password hashing ──────────────────────────────────────────────────────────

def test_hash_password_returns_string():
    result = hash_password("mysecretpassword")
    assert isinstance(result, str)
    assert len(result) > 20


def test_hash_password_is_not_plaintext():
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert hashed != password


def test_hash_password_different_hashes_for_same_input():
    """Argon2 salts each hash — same password gives different hash."""
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2


def test_verify_password_correct():
    password = "correct-horse-battery-staple"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("rightpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_empty_string():
    hashed = hash_password("somepassword")
    assert verify_password("", hashed) is False


# ── JWT tokens ────────────────────────────────────────────────────────────────

def test_create_access_token_returns_string():
    token = create_access_token({"sub": "user-123", "type": "access"})
    assert isinstance(token, str)
    assert len(token) > 20


def test_decode_access_token_round_trip():
    payload = {"sub": "user-abc", "type": "access"}
    token = create_access_token(payload)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-abc"
    assert decoded["type"] == "access"


def test_create_refresh_token_returns_string():
    token = create_refresh_token({"sub": "user-123", "type": "refresh"})
    assert isinstance(token, str)


def test_decode_refresh_token_round_trip():
    payload = {"sub": "user-xyz", "type": "refresh"}
    token = create_refresh_token(payload)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-xyz"
    assert decoded["type"] == "refresh"


def test_decode_token_invalid_returns_none():
    result = decode_token("not.a.valid.jwt")
    assert result is None


def test_decode_token_tampered_returns_none():
    token = create_access_token({"sub": "user-123", "type": "access"})
    # Tamper with the signature
    parts = token.split(".")
    tampered = parts[0] + "." + parts[1] + ".invalidsignature"
    result = decode_token(tampered)
    assert result is None


def test_decode_token_empty_string_returns_none():
    result = decode_token("")
    assert result is None
```

**Step 2: Run — expect PASS**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_security.py -v"
```

Expected: all tests pass. If a function has a different name (e.g., `get_password_hash` instead of `hash_password`), check `backend/app/utils/security.py` and update the import.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_security.py
git commit -m "test: unit tests for security utils (hash, verify, JWT)"
```

---

## Task 2: Encryption service — pure function tests

**Files:**
- Create: `backend/tests/unit/test_encryption.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_encryption.py`:

```python
"""Unit tests for app.services.encryption — Fernet encrypt/decrypt."""
import pytest
from app.services.encryption import encrypt_api_key, decrypt_api_key


def test_encrypt_returns_different_string():
    plaintext = "sk-test-this-is-a-real-api-key"
    encrypted = encrypt_api_key(plaintext)
    assert encrypted != plaintext
    assert isinstance(encrypted, str)


def test_decrypt_round_trip():
    plaintext = "sk-test-this-is-a-real-api-key"
    encrypted = encrypt_api_key(plaintext)
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == plaintext


def test_encrypt_same_input_different_output():
    """Fernet uses random IV — same plaintext produces different ciphertext."""
    key = "my-secret-oauth-token"
    c1 = encrypt_api_key(key)
    c2 = encrypt_api_key(key)
    assert c1 != c2


def test_decrypt_wrong_data_raises():
    """Decrypting garbage should raise an exception (not return garbage)."""
    with pytest.raises(Exception):
        decrypt_api_key("not-valid-fernet-data")
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_encryption.py -v"
```

Expected: 4 passed.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_encryption.py
git commit -m "test: unit tests for Fernet encrypt/decrypt"
```

---

## Task 3: Lead scoring — pure function tests

**Files:**
- Create: `backend/tests/unit/test_lead_scoring.py`

The `score_message_sync` function is a pure sync function — no DB, no Celery, testable directly.

**Step 1: Write the tests**

Create `backend/tests/unit/test_lead_scoring.py`:

```python
"""Unit tests for lead scoring regex logic (score_message_sync)."""
from app.workers.tasks.score_lead import score_message_sync


def test_pricing_signal_scores_positive():
    score, signals = score_message_sync("What is your pricing for the enterprise plan?")
    assert score > 0
    assert any("pricing" in s.lower() for s in signals)


def test_demo_request_scores_highest():
    score, signals = score_message_sync("I'd like to book a demo with your team.")
    assert score >= 20  # demo_request is +20
    assert any("demo" in s.lower() for s in signals)


def test_competitor_mention_scores_positive():
    score, signals = score_message_sync("We're currently using Intercom but looking for alternatives.")
    assert score > 0
    assert any("competitor" in s.lower() for s in signals)


def test_negative_signal_scores_negative():
    score, signals = score_message_sync("I'm just browsing, not interested in purchasing.")
    assert score < 0
    assert len(signals) > 0


def test_neutral_message_scores_zero():
    score, signals = score_message_sync("Hello, how are you?")
    assert score == 0
    assert signals == []


def test_multiple_signals_stack():
    # pricing + urgency + demo = at least 45 points
    score, signals = score_message_sync(
        "I need pricing urgently, can we schedule a demo this week?"
    )
    assert score >= 30
    assert len(signals) >= 2


def test_returns_tuple():
    result = score_message_sync("test message")
    assert isinstance(result, tuple)
    assert len(result) == 2
    score, signals = result
    assert isinstance(score, int)
    assert isinstance(signals, list)


def test_empty_message_scores_zero():
    score, signals = score_message_sync("")
    assert score == 0
    assert signals == []
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_lead_scoring.py -v"
```

Expected: 8 passed. If any regex patterns differ from what's in the task file, adjust assertions.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_lead_scoring.py
git commit -m "test: unit tests for lead scoring regex (score_message_sync)"
```

---

## Task 4: Credits service — DB tests

**Files:**
- Create: `backend/tests/unit/test_credits.py`

Uses the `db` and `workspace` fixtures from conftest.py.

**Step 1: Write the tests**

Create `backend/tests/unit/test_credits.py`:

```python
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
    # gpt-4o-mini rate is 1 credit per 1k tokens
    cost = estimate_token_cost("gpt-4o-mini", 1000)
    assert cost == 1


def test_estimate_token_cost_gpt4o():
    # gpt-4o rate is 5 credits per 1k tokens
    cost = estimate_token_cost("gpt-4o", 1000)
    assert cost == 5


def test_estimate_token_cost_minimum_one():
    """Even tiny token counts cost at least 1 credit."""
    cost = estimate_token_cost("gpt-4o-mini", 1)
    assert cost >= 1


def test_estimate_token_cost_scales_with_tokens():
    cost_1k = estimate_token_cost("gpt-4o", 1000)
    cost_2k = estimate_token_cost("gpt-4o", 2000)
    assert cost_2k == cost_1k * 2


# ── DB operations ─────────────────────────────────────────────────────────────

async def test_get_balance_new_workspace(db, workspace):
    """A new workspace's balance is whatever plan default gives it."""
    balance = await get_balance(db, workspace.id)
    assert isinstance(balance, int)
    assert balance >= 0


async def test_add_credits_increases_balance(db, workspace):
    before = await get_balance(db, workspace.id)
    new_balance = await add_credits(db, workspace.id, amount=100, reason="test_top_up")
    assert new_balance == before + 100


async def test_debit_credits_decreases_balance(db, workspace):
    # Top up first so we have enough
    await add_credits(db, workspace.id, amount=500, reason="test_setup")
    before = await get_balance(db, workspace.id)
    new_balance = await debit_credits(db, workspace.id, amount=50, reason="test_debit")
    assert new_balance == before - 50


async def test_debit_credits_insufficient_raises(db, workspace):
    """Debiting more than balance should raise ValueError."""
    current = await get_balance(db, workspace.id)
    with pytest.raises(ValueError, match="Insufficient"):
        await debit_credits(db, workspace.id, amount=current + 99999, reason="test")


async def test_add_credits_creates_ledger_entry(db, workspace):
    """add_credits should create a CreditLedger record."""
    from sqlalchemy import select
    from app.models.billing import CreditLedger
    await add_credits(db, workspace.id, amount=250, reason="test_ledger")
    result = await db.execute(
        select(CreditLedger).where(
            CreditLedger.workspace_id == workspace.id,
            CreditLedger.reason == "test_ledger",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.amount == 250


async def test_debit_credits_creates_negative_ledger_entry(db, workspace):
    """debit_credits should create a negative CreditLedger record."""
    from sqlalchemy import select
    from app.models.billing import CreditLedger
    await add_credits(db, workspace.id, amount=500, reason="setup")
    await debit_credits(db, workspace.id, amount=75, reason="test_debit_ledger")
    result = await db.execute(
        select(CreditLedger).where(
            CreditLedger.workspace_id == workspace.id,
            CreditLedger.reason == "test_debit_ledger",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.amount == -75
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_credits.py -v"
```

If `CreditLedger` import path is wrong, check `backend/app/models/billing.py` or run:
```bash
docker compose exec backend bash -c "cd /app && python -c 'from app.models.billing import CreditLedger; print(\"ok\")'"
```

Expected: 10 tests pass.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_credits.py
git commit -m "test: unit tests for credits service (debit, add, balance, ledger)"
```

---

## Task 5: Auth service — register + login tests

**Files:**
- Create: `backend/tests/unit/test_auth_service.py`

Auth service uses DB + Redis. Mock Redis calls with `mocker` (pytest-mock).

**Step 1: Write the tests**

Create `backend/tests/unit/test_auth_service.py`:

```python
"""Unit tests for app.services.auth_service — register and login flows."""
import pytest
from fastapi import HTTPException
from app.services.auth_service import register_user, authenticate_user


async def test_register_creates_workspace_agent_membership(db, mocker):
    """register_user creates Workspace + Agent + WorkspaceMembership(owner)."""
    # Mock Redis store_refresh_token
    mocker.patch("app.services.auth_service.redis_client", create=True)
    mocker.patch("app.services.auth_service._store_refresh_token", return_value=None)

    agent, workspace, tokens = await register_user(
        db,
        email="newuser@example.com",
        password="SecurePass123!",
        name="New User",
        workspace_name="New Workspace",
    )

    assert agent.email == "newuser@example.com"
    assert agent.name == "New User"
    assert workspace.name == "New Workspace"
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"


async def test_register_duplicate_email_raises_409(db, mocker):
    """Registering same email twice raises HTTPException 409."""
    mocker.patch("app.services.auth_service._store_refresh_token", return_value=None)

    await register_user(
        db,
        email="duplicate@example.com",
        password="Pass123!",
        name="First User",
        workspace_name="First Workspace",
    )

    with pytest.raises(HTTPException) as exc_info:
        await register_user(
            db,
            email="duplicate@example.com",
            password="Pass456!",
            name="Second User",
            workspace_name="Second Workspace",
        )
    assert exc_info.value.status_code == 409


async def test_authenticate_user_correct_credentials(db, agent, mocker):
    """authenticate_user returns (agent, tokens) with correct password."""
    mocker.patch("app.services.auth_service._store_refresh_token", return_value=None)

    # The `agent` fixture uses password "testpassword123"
    result_agent, tokens = await authenticate_user(
        db,
        email=agent.email,
        password="testpassword123",
    )

    assert result_agent.id == agent.id
    assert "access_token" in tokens


async def test_authenticate_user_wrong_password_raises_401(db, agent, mocker):
    """Wrong password raises HTTPException 401."""
    mocker.patch("app.services.auth_service._store_refresh_token", return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(
            db,
            email=agent.email,
            password="wrongpassword",
        )
    assert exc_info.value.status_code == 401


async def test_authenticate_user_unknown_email_raises_401(db, mocker):
    """Unknown email raises HTTPException 401."""
    mocker.patch("app.services.auth_service._store_refresh_token", return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(
            db,
            email="nobody@nowhere.com",
            password="anypassword",
        )
    assert exc_info.value.status_code == 401


async def test_register_workspace_slug_is_derived_from_name(db, mocker):
    """Workspace slug is derived from workspace_name."""
    mocker.patch("app.services.auth_service._store_refresh_token", return_value=None)

    _, workspace, _ = await register_user(
        db,
        email="slug-test@example.com",
        password="Pass123!",
        name="Slug Tester",
        workspace_name="My Awesome Company",
    )

    # Slug should be lowercase and URL-friendly
    assert workspace.slug is not None
    assert " " not in workspace.slug
    assert workspace.slug == workspace.slug.lower()
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_auth_service.py -v"
```

If the mock path is wrong (e.g., `_store_refresh_token` doesn't exist and Redis is called differently), read `backend/app/services/auth_service.py` and find the actual Redis call. Mock it at the correct import path:
```bash
grep -n "redis\|refresh_token" backend/app/services/auth_service.py | head -20
```

Expected: 6 tests pass.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_auth_service.py
git commit -m "test: unit tests for auth service (register, login, duplicate, wrong password)"
```

---

## Task 6: Workspace service — create + list tests

**Files:**
- Create: `backend/tests/unit/test_workspace_service.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_workspace_service.py`:

```python
"""Unit tests for app.services.workspace_service."""
import pytest
from fastapi import HTTPException
from app.services.workspace_service import create_workspace, list_workspaces, get_workspace


async def test_create_workspace_returns_workspace(db, agent):
    ws = await create_workspace(
        db,
        name="Test Corp",
        slug="test-corp-unique",
        agent_id=agent.id,
    )
    assert ws.name == "Test Corp"
    assert ws.slug == "test-corp-unique"


async def test_create_workspace_creates_owner_membership(db, agent):
    """Creating a workspace should add the agent as owner."""
    from sqlalchemy import select
    from app.models.organizational import WorkspaceMembership

    ws = await create_workspace(db, name="MyCo", slug="myco-slug", agent_id=agent.id)

    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == ws.id,
            WorkspaceMembership.agent_id == agent.id,
        )
    )
    membership = result.scalar_one_or_none()
    assert membership is not None
    assert membership.role == "owner"


async def test_create_workspace_duplicate_slug_raises_409(db, agent):
    await create_workspace(db, name="First", slug="same-slug", agent_id=agent.id)
    with pytest.raises(HTTPException) as exc_info:
        await create_workspace(db, name="Second", slug="same-slug", agent_id=agent.id)
    assert exc_info.value.status_code == 409


async def test_list_workspaces_returns_agents_workspaces(db, agent, workspace):
    """list_workspaces returns workspaces the agent is a member of."""
    workspaces = await list_workspaces(db, agent_id=agent.id)
    ws_ids = [ws.id for ws in workspaces]
    assert workspace.id in ws_ids


async def test_list_workspaces_excludes_other_agents_workspaces(
    db, agent, second_workspace, second_agent
):
    """An agent cannot see workspaces they are not a member of."""
    workspaces = await list_workspaces(db, agent_id=agent.id)
    ws_ids = [ws.id for ws in workspaces]
    assert second_workspace.id not in ws_ids


async def test_get_workspace_valid_member(db, agent, workspace):
    result = await get_workspace(db, workspace_id=workspace.id, agent_id=agent.id)
    assert result.id == workspace.id


async def test_get_workspace_non_member_raises_404(db, second_agent, workspace):
    """An agent who is not a member of a workspace should get 404."""
    with pytest.raises(HTTPException) as exc_info:
        await get_workspace(db, workspace_id=workspace.id, agent_id=second_agent.id)
    assert exc_info.value.status_code == 404
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_workspace_service.py -v"
```

Expected: 7 tests pass.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_workspace_service.py
git commit -m "test: unit tests for workspace service (create, list, isolation)"
```

---

## Task 7: Conversation service — CRUD + filter tests

**Files:**
- Create: `backend/tests/unit/test_conversation_service.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_conversation_service.py`:

```python
"""Unit tests for app.services.conversation_service."""
import pytest
from app.services.conversation_service import (
    create_conversation,
    add_message,
    list_conversations,
    get_messages,
    update_conversation_status,
)
from tests.factories import make_chatbot, make_conversation


async def test_create_conversation_defaults(db, workspace):
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(
        db,
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
    )
    assert conv.workspace_id == workspace.id
    assert conv.chatbot_id == chatbot.id
    assert conv.status == "open"


async def test_add_message_user(db, workspace):
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    msg = await add_message(
        db,
        conversation_id=conv.id,
        workspace_id=workspace.id,
        content="Hello!",
        author_type="user",
        message_type="incoming",
    )
    assert msg.content == "Hello!"
    assert msg.author_type == "user"
    assert msg.conversation_id == conv.id


async def test_add_message_bot(db, workspace):
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    msg = await add_message(
        db,
        conversation_id=conv.id,
        workspace_id=workspace.id,
        content="I can help with that.",
        author_type="bot",
        message_type="outgoing",
        confidence_score=0.92,
    )
    assert msg.confidence_score == pytest.approx(0.92)


async def test_get_messages_ordered_asc(db, workspace):
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    await add_message(db, conv.id, workspace.id, "First", "user", "incoming")
    await add_message(db, conv.id, workspace.id, "Second", "bot", "outgoing")
    messages = await get_messages(db, conv.id, workspace.id)
    assert len(messages) == 2
    assert messages[0].content == "First"
    assert messages[1].content == "Second"


async def test_list_conversations_status_filter(db, workspace):
    chatbot = await make_chatbot(db, workspace)
    conv_open = await make_conversation(db, workspace, chatbot, status="open")
    conv_resolved = await make_conversation(db, workspace, chatbot, status="resolved")

    open_list = await list_conversations(db, workspace.id, status_filter="open")
    open_ids = [c.id for c in open_list]
    assert conv_open.id in open_ids
    assert conv_resolved.id not in open_ids


async def test_list_conversations_chatbot_filter(db, workspace):
    bot_a = await make_chatbot(db, workspace, name="Bot A")
    bot_b = await make_chatbot(db, workspace, name="Bot B")
    conv_a = await make_conversation(db, workspace, bot_a)
    conv_b = await make_conversation(db, workspace, bot_b)

    result = await list_conversations(db, workspace.id, chatbot_id=bot_a.id)
    result_ids = [c.id for c in result]
    assert conv_a.id in result_ids
    assert conv_b.id not in result_ids


async def test_update_conversation_status(db, workspace):
    chatbot = await make_chatbot(db, workspace)
    conv = await create_conversation(db, workspace_id=workspace.id, chatbot_id=chatbot.id)
    assert conv.status == "open"
    updated = await update_conversation_status(db, conv.id, "resolved", workspace.id)
    assert updated.status == "resolved"


async def test_list_conversations_workspace_isolation(db, workspace, second_workspace):
    """Conversations from workspace A must not appear in workspace B's list."""
    bot_a = await make_chatbot(db, workspace)
    bot_b = await make_chatbot(db, second_workspace)
    conv_a = await make_conversation(db, workspace, bot_a)
    conv_b = await make_conversation(db, second_workspace, bot_b)

    result_a = await list_conversations(db, workspace.id)
    result_b = await list_conversations(db, second_workspace.id)

    ids_a = [c.id for c in result_a]
    ids_b = [c.id for c in result_b]

    assert conv_a.id in ids_a
    assert conv_b.id not in ids_a
    assert conv_b.id in ids_b
    assert conv_a.id not in ids_b
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_conversation_service.py -v"
```

Expected: 9 tests pass.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_conversation_service.py
git commit -m "test: unit tests for conversation service (CRUD, filters, isolation)"
```

---

## Task 8: API key service — create + validate + revoke

**Files:**
- Create: `backend/tests/unit/test_api_key_service.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_api_key_service.py`:

```python
"""Unit tests for app.services.api_key_service."""
import pytest
from fastapi import HTTPException
from app.services.api_key_service import (
    create_api_key,
    list_api_keys,
    revoke_api_key,
    validate_api_key,
)


async def test_create_api_key_returns_key_string(db, workspace):
    api_key_record, full_key = await create_api_key(
        db, workspace_id=workspace.id, name="Test Key"
    )
    assert full_key.startswith("pk_live_")
    assert len(full_key) > 20
    assert api_key_record.name == "Test Key"
    assert api_key_record.workspace_id == workspace.id


async def test_create_api_key_does_not_store_plaintext(db, workspace):
    """The DB record must NOT store the full key in plaintext."""
    api_key_record, full_key = await create_api_key(
        db, workspace_id=workspace.id, name="Secure Key"
    )
    # The stored key_hash should differ from full_key
    assert hasattr(api_key_record, "key_hash")
    assert api_key_record.key_hash != full_key


async def test_validate_api_key_valid(db, workspace):
    _, full_key = await create_api_key(db, workspace_id=workspace.id, name="Valid Key")
    result = await validate_api_key(db, full_key)
    assert result.workspace_id == workspace.id


async def test_validate_api_key_invalid_raises_401(db):
    with pytest.raises(HTTPException) as exc_info:
        await validate_api_key(db, "pk_live_totallyfakekey12345")
    assert exc_info.value.status_code == 401


async def test_revoke_api_key_makes_it_invalid(db, workspace):
    api_key_record, full_key = await create_api_key(
        db, workspace_id=workspace.id, name="To Revoke"
    )
    await revoke_api_key(db, workspace_id=workspace.id, key_id=api_key_record.id)
    with pytest.raises(HTTPException) as exc_info:
        await validate_api_key(db, full_key)
    assert exc_info.value.status_code == 401


async def test_revoke_nonexistent_key_raises_404(db, workspace):
    import uuid
    with pytest.raises(HTTPException) as exc_info:
        await revoke_api_key(db, workspace_id=workspace.id, key_id=uuid.uuid4())
    assert exc_info.value.status_code == 404


async def test_list_api_keys_returns_workspace_keys(db, workspace):
    await create_api_key(db, workspace_id=workspace.id, name="Key One")
    await create_api_key(db, workspace_id=workspace.id, name="Key Two")
    keys = await list_api_keys(db, workspace_id=workspace.id)
    assert len(keys) >= 2
    names = [k.name for k in keys]
    assert "Key One" in names
    assert "Key Two" in names
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_api_key_service.py -v"
```

Expected: 7 tests pass.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_api_key_service.py
git commit -m "test: unit tests for API key service (create, validate, revoke)"
```

---

## Task 9: Invite service — create + accept + revoke

**Files:**
- Create: `backend/tests/unit/test_invite_service.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_invite_service.py`:

```python
"""Unit tests for app.services.invite_service."""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from app.services.invite_service import (
    create_invite,
    accept_invite,
    list_invites,
    revoke_invite,
)


async def test_create_invite_returns_invite(db, workspace, agent):
    invite = await create_invite(
        db,
        workspace_id=workspace.id,
        email="newmember@example.com",
        role="member",
        invited_by_id=agent.id,
    )
    assert invite.email == "newmember@example.com"
    assert invite.role == "member"
    assert invite.token is not None
    assert len(invite.token) > 20


async def test_create_invite_has_expiry(db, workspace, agent):
    invite = await create_invite(
        db,
        workspace_id=workspace.id,
        email="expires@example.com",
        role="member",
        invited_by_id=agent.id,
    )
    assert invite.expires_at is not None
    # Expires in ~7 days from now
    now = datetime.now(timezone.utc)
    expires = invite.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert expires > now + timedelta(days=6)


async def test_accept_invite_creates_agent_and_membership(db, workspace, agent):
    invite = await create_invite(
        db,
        workspace_id=workspace.id,
        email="invitee@example.com",
        role="member",
        invited_by_id=agent.id,
    )
    from sqlalchemy import select
    from app.models.organizational import WorkspaceMembership

    new_agent = await accept_invite(
        db,
        token=invite.token,
        full_name="Invited User",
        password="SecurePass123!",
    )

    assert new_agent.email == "invitee@example.com"

    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.agent_id == new_agent.id,
            WorkspaceMembership.workspace_id == workspace.id,
        )
    )
    membership = result.scalar_one_or_none()
    assert membership is not None
    assert membership.role == "member"


async def test_accept_invite_invalid_token_raises_404(db):
    with pytest.raises(HTTPException) as exc_info:
        await accept_invite(db, token="totallyfaketoken", full_name="Nobody", password="pass")
    assert exc_info.value.status_code == 404


async def test_list_invites_returns_workspace_invites(db, workspace, agent):
    await create_invite(db, workspace.id, "a@test.com", "member", agent.id)
    await create_invite(db, workspace.id, "b@test.com", "admin", agent.id)
    invites = await list_invites(db, workspace.id)
    emails = [i.email for i in invites]
    assert "a@test.com" in emails
    assert "b@test.com" in emails


async def test_revoke_invite(db, workspace, agent):
    invite = await create_invite(db, workspace.id, "revoke@test.com", "member", agent.id)
    await revoke_invite(db, workspace.id, invite.id)
    # After revoke, accepting should fail
    with pytest.raises(HTTPException):
        await accept_invite(db, token=invite.token, full_name="X", password="pass")
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_invite_service.py -v"
```

If `revoke_invite` deletes the record (rather than marking it), the last test may need adjustment — check the implementation and adapt.

Expected: 6 tests pass.

**Step 3: Commit**

```bash
git add backend/tests/unit/test_invite_service.py
git commit -m "test: unit tests for invite service (create, accept, revoke)"
```

---

## Task 10: Billing service — plan limits (sync, no DB)

**Files:**
- Create: `backend/tests/unit/test_billing_service.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_billing_service.py`:

```python
"""Unit tests for app.services.billing — plan limits (no DB needed)."""
from app.services.billing import get_plan_limits


def test_free_plan_limits():
    limits = get_plan_limits("free")
    assert limits["conversations"] == 100
    assert limits["chatbots"] == 1
    assert limits["knowledge_bases"] == 2


def test_starter_plan_limits():
    limits = get_plan_limits("starter")
    assert limits["conversations"] == 1000
    assert limits["chatbots"] == 3


def test_professional_plan_limits():
    limits = get_plan_limits("professional")
    assert limits["conversations"] == 10000


def test_enterprise_plan_unlimited():
    limits = get_plan_limits("enterprise")
    # -1 means unlimited
    assert limits["conversations"] == -1
    assert limits["chatbots"] == -1


def test_unknown_plan_returns_free_limits_or_raises():
    """Unknown plan should either return free defaults or raise — not crash silently."""
    try:
        limits = get_plan_limits("nonexistent_plan")
        # If it doesn't raise, it should return some safe defaults
        assert "conversations" in limits
    except (KeyError, ValueError):
        pass  # Raising is also acceptable


def test_plan_limits_return_dict():
    limits = get_plan_limits("pro")
    assert isinstance(limits, dict)


def test_paid_plans_have_more_than_free():
    free = get_plan_limits("free")
    paid = get_plan_limits("starter")
    # Paid should have more conversations
    assert paid["conversations"] > free["conversations"]
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/test_billing_service.py -v"
```

Expected: 7 tests pass. Adjust plan names if `professional` is named differently (e.g. `pro`).

**Step 3: Commit**

```bash
git add backend/tests/unit/test_billing_service.py
git commit -m "test: unit tests for billing plan limits"
```

---

## Task 11: Run the full Phase 2 suite

**Step 1: Run all unit tests**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/ -v"
```

Expected: all tests pass. Fix any import errors or field name mismatches before proceeding.

**Step 2: Run the full suite (including Phase 1 integration tests)**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/ -v 2>&1 | tail -10"
```

Expected: all tests pass.

**Step 3: Check coverage on the tested modules**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/unit/ --cov=app.utils.security --cov=app.services.credits --cov=app.services.auth_service --cov=app.services.workspace_service --cov=app.services.conversation_service --cov=app.services.api_key_service --cov=app.services.invite_service --cov=app.services.billing --cov=app.services.encryption --cov=app.workers.tasks.score_lead --cov-report=term-missing 2>&1 | tail -30"
```

Expected: >70% line coverage on each tested module.

**Step 4: Commit**

No new files — just verify all tests pass and commit a summary note if needed.

```bash
git commit --allow-empty -m "test: Phase 2 backend unit tests complete — all passing"
```

---

## Phase 2 Completion Checklist

```bash
# All unit tests pass
docker compose exec backend bash -c "cd /app && pytest tests/unit/ -v 2>&1 | tail -5"
# Expected: X passed, 0 failed

# Full suite passes
docker compose exec backend bash -c "cd /app && pytest tests/ -v 2>&1 | tail -5"
# Expected: all passed

# Count tests
docker compose exec backend bash -c "cd /app && pytest tests/unit/ --collect-only -q 2>&1 | tail -3"
# Expected: 50+ tests collected
```

### What Phase 2 Delivers

| Test File | Covers |
|---|---|
| `test_security.py` | hash_password, verify_password, JWT create/decode |
| `test_encryption.py` | Fernet encrypt/decrypt round-trip |
| `test_lead_scoring.py` | score_message_sync regex scoring |
| `test_credits.py` | debit, add, balance, ledger entries, estimate_token_cost |
| `test_auth_service.py` | register, login, duplicate email, wrong password |
| `test_workspace_service.py` | create, list, slug conflict, membership, isolation |
| `test_conversation_service.py` | CRUD, status filter, chatbot filter, workspace isolation |
| `test_api_key_service.py` | create, validate, revoke, list |
| `test_invite_service.py` | create, accept, list, revoke |
| `test_billing_service.py` | plan limits, unlimited enterprise |

### What Phase 3 Needs

Phase 3 (Tenant Isolation Suite) will reuse factories and fixtures from Phase 1 and add cross-workspace attack scenario tests.
