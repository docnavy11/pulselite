# Testing Phase 4 — API Integration Tests

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Test the full HTTP request-response cycle for every major API surface — verifying status codes, response body shapes, pagination, error messages, and header requirements at the HTTP boundary (not just service-layer logic).

**Architecture:** Each test file covers one API domain. Tests use `auth_client` (authenticated httpx client) and real DB with SAVEPOINT rollback. These differ from Phase 2 unit tests: they go through the full FastAPI routing stack, validate JSON shapes, and check that routers correctly transform service results. External calls (Stripe, OpenAI, Celery) are mocked where needed.

**Tech Stack:** pytest-asyncio, httpx AsyncClient, pytest-mock, real pulse_test DB, real FastAPI app

---

## Before You Start

```bash
docker compose exec backend bash -c "cd /app && pytest tests/ -q 2>&1 | tail -3"
# Expected: 164 passed
```

---

## Task 1: Auth API — register, login, refresh

**Files:**
- Create: `backend/tests/integration/test_auth_api.py`

Tests the HTTP layer of authentication — status codes, response shapes, token presence. Mocks Redis.

**Step 1: Read the auth router**

```bash
grep -n "@router\|async def " backend/app/api/v1/auth.py | head -30
```

**Step 2: Create `backend/tests/integration/test_auth_api.py`**

```python
"""Integration tests for POST /auth/register, /auth/login, /auth/refresh."""
import pytest
from unittest.mock import AsyncMock


@pytest.fixture(autouse=True)
def mock_redis(mocker):
    """Silence Redis calls in all tests in this file."""
    mocker.patch("app.services.auth_service.redis_client.set", new_callable=AsyncMock)
    mocker.patch("app.services.auth_service.redis_client.get", new_callable=AsyncMock, return_value=None)


# ── Register ──────────────────────────────────────────────────────────────────

async def test_register_returns_201(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "reg@test.com",
        "password": "SecurePass123!",
        "name": "Reg User",
        "workspace_name": "Reg Workspace",
    })
    assert r.status_code == 201


async def test_register_response_has_tokens(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "tokens@test.com",
        "password": "SecurePass123!",
        "name": "Token User",
        "workspace_name": "Token WS",
    })
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data.get("token_type") == "bearer"


async def test_register_response_has_user(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "user@test.com",
        "password": "SecurePass123!",
        "name": "Some User",
        "workspace_name": "Some WS",
    })
    assert r.status_code == 201
    data = r.json()
    assert "user" in data
    assert data["user"]["email"] == "user@test.com"


async def test_register_duplicate_email_returns_409(client):
    payload = {"email": "dup@test.com", "password": "Pass123!", "name": "A", "workspace_name": "W"}
    await client.post("/api/v1/auth/register", json=payload)
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409


async def test_register_missing_field_returns_422(client):
    r = await client.post("/api/v1/auth/register", json={"email": "x@x.com"})
    assert r.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

async def test_login_correct_credentials_returns_200(client, agent):
    r = await client.post("/api/v1/auth/login", json={
        "email": agent.email,
        "password": "testpassword123",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data


async def test_login_wrong_password_returns_401(client, agent):
    r = await client.post("/api/v1/auth/login", json={
        "email": agent.email,
        "password": "wrongpassword",
    })
    assert r.status_code == 401


async def test_login_unknown_email_returns_401(client):
    r = await client.post("/api/v1/auth/login", json={
        "email": "nobody@nowhere.com",
        "password": "anypassword",
    })
    assert r.status_code == 401


async def test_login_missing_fields_returns_422(client):
    r = await client.post("/api/v1/auth/login", json={"email": "x@x.com"})
    assert r.status_code == 422
```

**Step 3: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_auth_api.py -v"
```

Check the actual response body if a test fails — `print(r.json())` or check `r.text`.

**Step 4: Commit**

```bash
git add backend/tests/integration/test_auth_api.py
git commit -m "test: integration tests for auth API (register, login)"
```

---

## Task 2: Chatbot API — full CRUD

**Files:**
- Create: `backend/tests/integration/test_chatbot_api.py`

**Step 1: Read chatbot router to find exact field names**

```bash
grep -n "class.*Request\|class.*Response\|BaseModel" backend/app/schemas/chatbots.py 2>/dev/null || \
grep -rn "class.*Request\|ChatbotCreate\|ChatbotUpdate" backend/app/schemas/ | head -20
```

**Step 2: Create `backend/tests/integration/test_chatbot_api.py`**

```python
"""Integration tests for /workspaces/{workspace_id}/chatbots CRUD."""
from tests.factories import make_chatbot


async def test_list_chatbots_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_chatbot_returns_201(auth_client, workspace):
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={
            "name": "My Bot",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My Bot"
    assert "id" in data


async def test_create_chatbot_appears_in_list(auth_client, workspace):
    await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Listed Bot", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
    )
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots")
    names = [c["name"] for c in r.json()]
    assert "Listed Bot" in names


async def test_get_chatbot_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace, name="Fetch Me")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Fetch Me"


async def test_get_nonexistent_chatbot_returns_404(auth_client, workspace):
    import uuid
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/chatbots/{uuid.uuid4()}"
    )
    assert r.status_code == 404


async def test_update_chatbot_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace, name="Old Name")
    r = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}",
        json={"name": "New Name"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


async def test_delete_chatbot_returns_204(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace, name="Delete Me")
    r = await auth_client.delete(
        f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}"
    )
    assert r.status_code == 204


async def test_delete_chatbot_then_get_returns_404(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace, name="Gone Bot")
    await auth_client.delete(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
    assert r.status_code == 404


async def test_chatbot_response_has_required_fields(auth_client, workspace):
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/chatbots",
        json={"name": "Field Bot", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
    )
    data = r.json()
    for field in ("id", "name", "workspace_id", "llm_provider", "llm_model"):
        assert field in data, f"Missing field: {field}"
```

**Step 3: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_chatbot_api.py -v"
```

If the create endpoint requires different fields (read the 422 error body), adjust the JSON payload.

**Step 4: Commit**

```bash
git add backend/tests/integration/test_chatbot_api.py
git commit -m "test: integration tests for chatbot API (CRUD + field validation)"
```

---

## Task 3: Knowledge Base API — CRUD

**Files:**
- Create: `backend/tests/integration/test_knowledge_base_api.py`

**Step 1: Check what fields are required to create a KB**

```bash
grep -n "KnowledgeBaseCreate\|class.*KB\|name.*required\|chatbot_id" backend/app/schemas/ -r | head -20
```

**Step 2: Create `backend/tests/integration/test_knowledge_base_api.py`**

```python
"""Integration tests for /workspaces/{workspace_id}/knowledge-bases CRUD."""
from tests.factories import make_chatbot, make_knowledge_base


async def test_list_knowledge_bases_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_knowledge_base_returns_201(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases",
        json={"name": "My KB", "chatbot_id": str(bot.id)},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My KB"
    assert "id" in data


async def test_get_knowledge_base_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    kb = await make_knowledge_base(db, workspace, bot, name="Fetch KB")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb.id}"
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Fetch KB"


async def test_get_nonexistent_kb_returns_404(auth_client, workspace):
    import uuid
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{uuid.uuid4()}"
    )
    assert r.status_code == 404


async def test_delete_knowledge_base_returns_204(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    kb = await make_knowledge_base(db, workspace, bot, name="Delete KB")
    r = await auth_client.delete(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb.id}"
    )
    assert r.status_code == 204


async def test_delete_kb_then_get_returns_404(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    kb = await make_knowledge_base(db, workspace, bot, name="Gone KB")
    await auth_client.delete(f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb.id}")
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb.id}")
    assert r.status_code == 404


async def test_list_kbs_scoped_to_chatbot(db, auth_client, workspace):
    bot_a = await make_chatbot(db, workspace, name="Bot A")
    bot_b = await make_chatbot(db, workspace, name="Bot B")
    kb_a = await make_knowledge_base(db, workspace, bot_a, name="KB A")
    await make_knowledge_base(db, workspace, bot_b, name="KB B")

    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/knowledge-bases?chatbot_id={bot_a.id}"
    )
    assert r.status_code == 200
    ids = [kb["id"] for kb in r.json()]
    assert str(kb_a.id) in ids
```

**Step 3: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_knowledge_base_api.py -v"
```

**Step 4: Commit**

```bash
git add backend/tests/integration/test_knowledge_base_api.py
git commit -m "test: integration tests for knowledge base API (CRUD)"
```

---

## Task 4: Conversations API — list, filters, export

**Files:**
- Create: `backend/tests/integration/test_conversations_api.py`

**Step 1: Create `backend/tests/integration/test_conversations_api.py`**

```python
"""Integration tests for /workspaces/{workspace_id}/conversations."""
from tests.factories import make_chatbot, make_conversation, make_message


async def test_list_conversations_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/conversations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_conversations_status_filter(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv_open = await make_conversation(db, workspace, bot, status="open")
    conv_resolved = await make_conversation(db, workspace, bot, status="resolved")

    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations?status=open"
    )
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert str(conv_open.id) in ids
    assert str(conv_resolved.id) not in ids


async def test_list_conversations_chatbot_filter(db, auth_client, workspace):
    bot_a = await make_chatbot(db, workspace, name="A")
    bot_b = await make_chatbot(db, workspace, name="B")
    conv_a = await make_conversation(db, workspace, bot_a)
    conv_b = await make_conversation(db, workspace, bot_b)

    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations?chatbot_id={bot_a.id}"
    )
    ids = [c["id"] for c in r.json()]
    assert str(conv_a.id) in ids
    assert str(conv_b.id) not in ids


async def test_get_conversation_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot)
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/{conv.id}"
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(conv.id)


async def test_get_nonexistent_conversation_returns_404(auth_client, workspace):
    import uuid
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/{uuid.uuid4()}"
    )
    assert r.status_code == 404


async def test_get_conversation_messages(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(db, workspace, bot)
    await make_message(db, conv, workspace, content="Hello")
    await make_message(db, conv, workspace, content="World", author_type="bot")

    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/{conv.id}/messages"
    )
    assert r.status_code == 200
    messages = r.json()
    assert len(messages) == 2
    assert messages[0]["content"] == "Hello"


async def test_export_conversations_returns_csv(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    await make_conversation(db, workspace, bot)
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/conversations/export"
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


async def test_conversations_response_has_required_fields(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    await make_conversation(db, workspace, bot)
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/conversations")
    assert r.status_code == 200
    convs = r.json()
    if convs:
        for field in ("id", "workspace_id", "status", "created_at"):
            assert field in convs[0], f"Missing field: {field}"
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_conversations_api.py -v"
```

If the messages endpoint has a different path (e.g., nested under conversation detail rather than `/messages`), check:
```bash
grep -n "@router\|/messages" backend/app/api/v1/chat.py | head -20
```

**Step 3: Commit**

```bash
git add backend/tests/integration/test_conversations_api.py
git commit -m "test: integration tests for conversations API (list, filters, messages, export)"
```

---

## Task 5: Exceptions API — list, detail, resolve, reply

**Files:**
- Create: `backend/tests/integration/test_exceptions_api.py`

**Step 1: Create `backend/tests/integration/test_exceptions_api.py`**

```python
"""Integration tests for /workspaces/{workspace_id}/exceptions."""
from tests.factories import make_chatbot, make_conversation, make_message


async def test_list_exceptions_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    assert r.status_code == 200
    data = r.json()
    # Response is {items: [], total: N}
    assert "items" in data
    assert "total" in data


async def test_list_exceptions_only_includes_escalated_or_unresolved(
    db, auth_client, workspace
):
    bot = await make_chatbot(db, workspace)
    # Autonomous resolved conversation — should NOT appear in exceptions
    conv_ok = await make_conversation(db, workspace, bot, autonomous_resolved=True)
    # Escalated conversation — SHOULD appear
    conv_exc = await make_conversation(
        db, workspace, bot, escalation_reason="low_confidence", autonomous_resolved=False
    )

    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
    ids = [item["id"] for item in r.json()["items"]]
    assert str(conv_exc.id) in ids
    assert str(conv_ok.id) not in ids


async def test_get_exception_detail_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(
        db, workspace, bot, escalation_reason="low_confidence"
    )
    await make_message(db, conv, workspace, content="Help me")
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}"
    )
    assert r.status_code == 200
    data = r.json()
    assert "conversation" in data
    assert "messages" in data


async def test_get_nonexistent_exception_returns_404(auth_client, workspace):
    import uuid
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{uuid.uuid4()}"
    )
    assert r.status_code == 404


async def test_resolve_exception_returns_200(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(
        db, workspace, bot, escalation_reason="low_confidence"
    )
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}/resolve"
    )
    assert r.status_code == 200


async def test_reply_to_exception_returns_201(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(
        db, workspace, bot, escalation_reason="low_confidence"
    )
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}/reply",
        json={"content": "Hi, I can help you with that.", "resolve": False},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "ok"


async def test_reply_with_resolve_closes_conversation(db, auth_client, workspace):
    bot = await make_chatbot(db, workspace)
    conv = await make_conversation(
        db, workspace, bot, escalation_reason="low_confidence"
    )
    r = await auth_client.post(
        f"/api/v1/workspaces/{workspace.id}/exceptions/{conv.id}/reply",
        json={"content": "Resolved your issue!", "resolve": True},
    )
    assert r.status_code == 201
    assert r.json()["resolved"] is True
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_exceptions_api.py -v"
```

Note: `list_exceptions` filters by `status == "open"` AND `(escalation_reason IS NOT NULL OR autonomous_resolved == False)`. Make sure test conversations have `status="open"` (the factory default).

**Step 3: Commit**

```bash
git add backend/tests/integration/test_exceptions_api.py
git commit -m "test: integration tests for exceptions API (list, detail, resolve, reply)"
```

---

## Task 6: Credits API — balance and history

**Files:**
- Create: `backend/tests/integration/test_credits_api.py`

**Step 1: Create `backend/tests/integration/test_credits_api.py`**

```python
"""Integration tests for /workspaces/{workspace_id}/credits/* endpoints."""


async def test_get_credits_balance_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
    assert r.status_code == 200
    data = r.json()
    assert "balance" in data
    assert isinstance(data["balance"], int)


async def test_credits_balance_response_shape(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
    data = r.json()
    # Must have balance and used_this_month (the billing fix from architectural review)
    assert "balance" in data
    assert "used_this_month" in data


async def test_get_credits_history_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/history")
    assert r.status_code == 200
    data = r.json()
    # History endpoint returns a list or {items: [], total: N}
    assert isinstance(data, (list, dict))


async def test_credits_balance_is_non_negative(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
    assert r.json()["balance"] >= 0
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_credits_api.py -v"
```

**Step 3: Commit**

```bash
git add backend/tests/integration/test_credits_api.py
git commit -m "test: integration tests for credits API (balance, history)"
```

---

## Task 7: Dashboard API — smoke tests

**Files:**
- Create: `backend/tests/integration/test_dashboard_api.py`

**Step 1: Create `backend/tests/integration/test_dashboard_api.py`**

```python
"""Integration tests for dashboard/analytics endpoints."""


async def test_dashboard_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
    assert r.status_code == 200


async def test_sentiment_trends_returns_200(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/sentiment-trends?days=7"
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data


async def test_resolution_stats_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/resolution-stats")
    assert r.status_code == 200


async def test_leads_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/leads")
    assert r.status_code == 200


async def test_topics_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/topics")
    assert r.status_code == 200


async def test_gap_events_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/gap-events")
    assert r.status_code == 200


async def test_feature_requests_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/feature-requests")
    assert r.status_code == 200


async def test_chats_by_country_returns_200(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/analytics/chats-by-country"
    )
    assert r.status_code == 200


async def test_sentiment_by_segment_returns_200(auth_client, workspace):
    r = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/sentiment-by-segment?days=7"
    )
    assert r.status_code == 200
```

**Step 2: Run**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_dashboard_api.py -v"
```

**Step 3: Commit**

```bash
git add backend/tests/integration/test_dashboard_api.py
git commit -m "test: integration smoke tests for dashboard and analytics endpoints"
```

---

## Task 8: Run full suite + coverage report

**Step 1: Run all tests**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/ -q 2>&1 | tail -5"
```

Expected: 220+ passed, 0 failed.

**Step 2: Coverage on the API layer**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/ --cov=app.api --cov-report=term-missing -q 2>&1 | grep -E 'TOTAL|app/api' | head -20"
```

**Step 3: Commit summary**

```bash
git commit --allow-empty -m "test: Phase 4 API integration tests complete"
```

---

## Phase 4 Completion Checklist

| Check | Expected |
|---|---|
| Auth API | register 201, login 200/401, dup 409 |
| Chatbot API | CRUD 201/200/204, 404 on missing |
| KB API | CRUD 201/200/204, chatbot filter |
| Conversations API | list + filters, messages, CSV export |
| Exceptions API | list filter, detail shape, resolve, reply |
| Credits API | balance shape with `used_this_month` |
| Dashboard API | all 9 endpoints return 200 |

### What Phase 5 Needs

Phase 5 (Frontend Unit Tests — Vitest + MSW) is independent of Phase 4. Phase 4's API response shape tests confirm what MSW mock handlers should return in Phase 5.
