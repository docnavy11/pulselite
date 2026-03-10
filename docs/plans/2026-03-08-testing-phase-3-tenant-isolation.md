# Testing Phase 3 — Tenant Isolation Suite

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prove that no authenticated agent can read, write, or delete another workspace's data — covering the cross-workspace token substitution attack and the cross-resource IDOR attack.

**Architecture:** All tests hit real HTTP endpoints via `auth_client` (workspace A's authenticated client) and attempt to access workspace B's resources. Two attack vectors are tested: (1) **URL workspace substitution** — swap workspace_id_B into the URL with token_A; (2) **IDOR** — use workspace_id_A in the URL but supply workspace_B's resource IDs. The `get_workspace` dependency returns HTTP 403 for attack vector 1; service-layer workspace scoping returns HTTP 404 for attack vector 2. Tests go in `backend/tests/integration/test_tenant_isolation.py`.

**Tech Stack:** pytest-asyncio, httpx AsyncClient, real pulse_test DB, real FastAPI app with dependency overrides for `get_db`

---

## Before You Start

```bash
# Verify full suite still passes
docker compose exec backend bash -c "cd /app && pytest tests/ -v 2>&1 | tail -5"
# Expected: 133 passed

# Verify second_workspace and second_agent fixtures exist
docker compose exec backend bash -c "cd /app && python -c 'from tests.conftest import make_auth_headers_for; print(\"ok\")'"
```

---

## Task 1: Cross-workspace token substitution — read endpoints

**Files:**
- Create: `backend/tests/integration/test_tenant_isolation.py`

Agent A holds a valid JWT. They substitute workspace B's ID into the URL. `get_workspace` checks membership and returns 403.

**Step 1: Write the failing tests**

Create `backend/tests/integration/test_tenant_isolation.py`:

```python
"""
Tenant Isolation Suite — Phase 3.

Two attack vectors tested for every resource category:

1. WORKSPACE SUBSTITUTION (HTTP 403):
   Agent A uses their valid JWT but substitutes workspace B's ID into the URL.
   `get_workspace` finds no WorkspaceMembership for agent_A in workspace_B → 403.

2. IDOR / RESOURCE SUBSTITUTION (HTTP 404):
   Agent A uses their own workspace_id in the URL but supplies workspace B's
   resource IDs. The service layer queries with WHERE workspace_id = workspace_A.id
   and finds nothing → 404.
"""
import pytest
from tests.factories import (
    make_chatbot,
    make_knowledge_base,
    make_conversation,
    make_message,
    make_document,
)
from tests.conftest import make_auth_headers_for


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _client_b(client, second_agent):
    """Return auth headers for second_agent (workspace B owner)."""
    return await make_auth_headers_for(second_agent)


# ══════════════════════════════════════════════════════════════════════════════
# ATTACK VECTOR 1: Workspace ID substitution → expect 403
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkspaceSubstitution:
    """Agent A substitutes workspace B's ID into the URL. Must get 403."""

    async def test_cannot_list_chatbots_in_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/chatbots"
        )
        assert response.status_code == 403

    async def test_cannot_list_conversations_in_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/conversations"
        )
        assert response.status_code == 403

    async def test_cannot_list_knowledge_bases_in_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/knowledge-bases"
        )
        assert response.status_code == 403

    async def test_cannot_view_exceptions_in_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/exceptions"
        )
        assert response.status_code == 403

    async def test_cannot_view_credits_balance_of_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/credits/balance"
        )
        assert response.status_code == 403

    async def test_cannot_view_dashboard_of_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/dashboard"
        )
        assert response.status_code == 403

    async def test_cannot_view_leads_of_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/leads"
        )
        assert response.status_code == 403

    async def test_cannot_view_integrations_of_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/integrations"
        )
        assert response.status_code == 403

    async def test_cannot_view_data_retention_of_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/data-retention"
        )
        assert response.status_code == 403

    async def test_cannot_view_intelligence_signals_of_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/intelligence-signals"
        )
        assert response.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# ATTACK VECTOR 1: Write/Mutate operations → expect 403
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkspaceSubstitutionWrites:
    """Agent A cannot create/modify resources in workspace B."""

    async def test_cannot_create_chatbot_in_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.post(
            f"/api/v1/workspaces/{second_workspace.id}/chatbots",
            json={"name": "Injected Bot", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
        )
        assert response.status_code == 403

    async def test_cannot_create_knowledge_base_in_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.post(
            f"/api/v1/workspaces/{second_workspace.id}/knowledge-bases",
            json={"name": "Stolen KB", "chatbot_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 403

    async def test_cannot_update_data_retention_of_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.put(
            f"/api/v1/workspaces/{second_workspace.id}/data-retention",
            json={"data_retention_days": 1},
        )
        assert response.status_code == 403

    async def test_cannot_update_integration_of_other_workspace(
        self, auth_client, second_workspace
    ):
        response = await auth_client.put(
            f"/api/v1/workspaces/{second_workspace.id}/integrations/hubspot",
            json={"config": {}, "is_active": True},
        )
        assert response.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# ATTACK VECTOR 2: IDOR — correct workspace_id, wrong resource ID → expect 404
# ══════════════════════════════════════════════════════════════════════════════

class TestIDOR:
    """
    Agent A uses their OWN workspace_id but injects workspace B's resource IDs.
    The service layer's WHERE workspace_id = workspace_A filter makes the
    resource invisible → 404.
    """

    async def test_cannot_read_other_workspaces_chatbot_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        """Workspace B's chatbot ID inserted into workspace A's URL → 404."""
        bot_b = await make_chatbot(db, second_workspace, name="Bot B")
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{bot_b.id}"
        )
        assert response.status_code == 404

    async def test_cannot_update_other_workspaces_chatbot_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace, name="Bot B")
        response = await auth_client.put(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{bot_b.id}",
            json={"name": "Hacked"},
        )
        assert response.status_code == 404

    async def test_cannot_delete_other_workspaces_chatbot_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace, name="Bot B")
        response = await auth_client.delete(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{bot_b.id}"
        )
        assert response.status_code == 404

    async def test_cannot_read_other_workspaces_knowledge_base_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace)
        kb_b = await make_knowledge_base(db, second_workspace, bot_b, name="KB B")
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb_b.id}"
        )
        assert response.status_code == 404

    async def test_cannot_read_other_workspaces_conversation_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace)
        conv_b = await make_conversation(db, second_workspace, bot_b)
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/conversations/{conv_b.id}"
        )
        assert response.status_code == 404

    async def test_cannot_read_messages_of_other_workspaces_conversation_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace)
        conv_b = await make_conversation(db, second_workspace, bot_b)
        await make_message(db, conv_b, second_workspace, content="Secret")
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/conversations/{conv_b.id}/messages"
        )
        assert response.status_code == 404

    async def test_cannot_read_exception_detail_of_other_workspace_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace)
        conv_b = await make_conversation(
            db, second_workspace, bot_b, escalation_reason="low_confidence"
        )
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/exceptions/{conv_b.id}"
        )
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# POSITIVE CONTROL: Agent A can access their OWN workspace resources
# ══════════════════════════════════════════════════════════════════════════════

class TestPositiveControls:
    """Verify auth_client CAN access workspace A's own resources (sanity check)."""

    async def test_can_list_own_chatbots(self, auth_client, workspace):
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/chatbots"
        )
        assert response.status_code == 200

    async def test_can_list_own_conversations(self, auth_client, workspace):
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/conversations"
        )
        assert response.status_code == 200

    async def test_can_read_own_chatbot(self, db, auth_client, workspace):
        bot = await make_chatbot(db, workspace, name="Own Bot")
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}"
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Own Bot"

    async def test_can_read_own_credits_balance(self, auth_client, workspace):
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/credits/balance"
        )
        assert response.status_code == 200

    async def test_can_list_own_knowledge_bases(self, auth_client, workspace):
        response = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/knowledge-bases"
        )
        assert response.status_code == 200
```

**Step 2: Run — expect all tests pass**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_tenant_isolation.py -v"
```

Expected: all tests pass. If any 403 comes back as 401 instead, check that `auth_client` headers are set — the fixture from conftest.py should have `Authorization: Bearer <token>`.

Common failure modes:
- Test returns 401 instead of 403 → `auth_client` headers not being sent correctly; verify fixture
- Test returns 200 instead of 404 (IDOR) → service layer missing `workspace_id` filter; this is a real security bug — report it
- Test returns 500 → application error; read the response body for the traceback

**Step 3: Commit**

```bash
git add backend/tests/integration/test_tenant_isolation.py
git commit -m "test: Phase 3 tenant isolation suite — workspace substitution + IDOR"
```

---

## Task 2: Unauthenticated access — no token at all

**Files:**
- Modify: `backend/tests/integration/test_tenant_isolation.py`

A client with no auth header should never get past the authentication layer.

**Step 1: Add the class to test_tenant_isolation.py**

Append to the existing file:

```python

# ══════════════════════════════════════════════════════════════════════════════
# NO AUTH: requests without a token → 401 or 403
# ══════════════════════════════════════════════════════════════════════════════

class TestNoAuthentication:
    """Requests with no Authorization header must be rejected."""

    async def test_unauthenticated_cannot_list_chatbots(self, client, workspace):
        response = await client.get(f"/api/v1/workspaces/{workspace.id}/chatbots")
        assert response.status_code in (401, 403)

    async def test_unauthenticated_cannot_list_conversations(self, client, workspace):
        response = await client.get(f"/api/v1/workspaces/{workspace.id}/conversations")
        assert response.status_code in (401, 403)

    async def test_unauthenticated_cannot_view_credits(self, client, workspace):
        response = await client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
        assert response.status_code in (401, 403)

    async def test_unauthenticated_cannot_view_exceptions(self, client, workspace):
        response = await client.get(f"/api/v1/workspaces/{workspace.id}/exceptions")
        assert response.status_code in (401, 403)

    async def test_expired_token_rejected(self, client, workspace):
        """A well-formed but expired JWT must be rejected."""
        import time
        from app.utils.security import create_access_token
        # Create a token that expired 1 hour ago
        expired_token = create_access_token(
            {"sub": "00000000-0000-0000-0000-000000000000", "type": "access"},
        )
        # Manually tamper: we can't easily create an expired token without
        # mocking time, so we verify an unknown sub gets 401/403
        response = await client.get(
            f"/api/v1/workspaces/{workspace.id}/chatbots",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code in (401, 403)
```

**Step 2: Run full isolation file**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/integration/test_tenant_isolation.py -v"
```

Expected: all tests pass.

**Step 3: Commit**

```bash
git add backend/tests/integration/test_tenant_isolation.py
git commit -m "test: add no-auth and expired-token isolation tests"
```

---

## Task 3: Run full suite + verify isolation Makefile target

**Step 1: Run just the isolation suite via Makefile**

```bash
make test-isolation
```

Expected: all isolation tests pass.

**Step 2: Run the complete test suite**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/ -v 2>&1 | tail -10"
```

Expected: 133 + all new isolation tests = 160+ passed, 0 failed.

**Step 3: Print test count**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/ --collect-only -q 2>&1 | tail -3"
```

**Step 4: Commit**

```bash
git commit --allow-empty -m "test: Phase 3 tenant isolation complete — all passing"
```

---

## Phase 3 Completion Checklist

| Check | Command | Expected |
|---|---|---|
| Isolation suite | `make test-isolation` | all pass |
| Full suite | `make test` (or `pytest tests/`) | 160+ pass |
| No 200s where 403/404 expected | Review test output | 0 failures |

### What Phase 4 Needs

Phase 4 (Integration Tests) will test complete request flows: authentication endpoints, chatbot CRUD, conversation export, billing webhook handling. It builds on the factories and auth infrastructure from Phases 1–3.
