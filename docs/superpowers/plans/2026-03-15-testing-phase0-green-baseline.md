# Phase 0: Green Baseline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 32 pre-existing test failures so the test suite is green before writing new tests.

**Architecture:** Each task fixes one root cause. Backend fixes update stale mocks to match refactored source code. Frontend fix updates the Zustand store mock to match the v4 subscribe API. No new tests — only fixing existing ones.

**Tech Stack:** pytest, unittest.mock, Vitest, vi.mock

**Spec:** `docs/superpowers/specs/2026-03-15-testing-strategy-design.md` (Phase 0)

---

## File Structure

| File | Action | What changes |
|------|--------|-------------|
| `backend/tests/unit/test_content_hash_skip.py` | Modify | Change mock embedding dimensions from 1536 to 384 |
| `backend/tests/unit/test_email_service.py` | Modify | Add `decrypt_api_key` mock (source now decrypts passwords/keys via Fernet) |
| `backend/tests/unit/test_emit_task_event.py` | Rewrite | Replace stale `_create_manager` mocks with mocks for current realtime architecture |
| `backend/tests/unit/test_realtime.py` | Rewrite | Replace stale `_create_manager` mocks with mocks for current realtime architecture |
| `backend/tests/unit/test_ingest_completion_check.py` | Modify | Add 5th mock execute result for workspace_id lookup + mock realtime calls |
| `frontend/src/test/socket.test.ts` | Modify | Add `subscribe` to workspace store mock, update auth to callback pattern, fix transports |
| `frontend/src/test/activity-console.test.ts` | Modify | Add `subscribe` to workspace store mock |
| `frontend/src/test/realtime-notifications.test.ts` | Modify | Add `subscribe` to workspace store mock |

---

### Task 1: Fix content hash skip tests (vector dimension mismatch)

**Files:**
- Modify: `backend/tests/unit/test_content_hash_skip.py:83,108,126`

**Root cause:** Mock embeddings use `[0.1] * 1536` but the DB column changed to 384 dimensions after the embedding model switch.

- [ ] **Step 1: Update mock embedding dimensions**

In `backend/tests/unit/test_content_hash_skip.py`, change all three occurrences of `[0.1] * 1536` to `[0.1] * 384`:

Line 83:
```python
mock_embeddings = [[0.1] * 384]
```

Line 108:
```python
mock_embeddings = [[0.1] * 384]
```

Line 126:
```python
mock_embeddings = [[0.1] * 384]
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_content_hash_skip.py -v`
Expected: All 6 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_content_hash_skip.py
git commit -m "fix(tests): update mock embedding dimensions from 1536 to 384"
```

---

### Task 2: Fix email service tests (missing decrypt_api_key mock)

**Files:**
- Modify: `backend/tests/unit/test_email_service.py`

**Root cause:** The `send_email` source code now calls `decrypt_api_key()` on SMTP passwords (line 54 of `email.py`) and Resend API keys (line 79). The tests pass plain strings that aren't valid Fernet tokens, causing decryption to fail silently and `send_email` to return `False`.

- [ ] **Step 1: Add decrypt_api_key mock to SMTP test**

Replace `test_send_email_smtp` in `backend/tests/unit/test_email_service.py`:

```python
def test_send_email_smtp():
    """SMTP provider sends via smtplib."""
    config = {
        "provider": "smtp",
        "host": "smtp.example.com",
        "port": 587,
        "username": "user@example.com",
        "password": "encrypted-secret",
        "tls": True,
        "from_email": "Pulse <noreply@example.com>",
        "to_email": "admin@example.com",
    }
    with patch("app.services.integrations.email.smtplib.SMTP") as mock_smtp, \
         patch("app.services.integrations.email.decrypt_api_key", return_value="secret"):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        result = send_email(config, "Test Subject", "<h1>Hello</h1>")
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "secret")
        mock_server.send_message.assert_called_once()
```

- [ ] **Step 2: Add decrypt_api_key mock to Resend tests**

Replace `test_send_email_resend` and `test_send_email_resend_explicit_provider`:

```python
def test_send_email_resend():
    """Resend provider (or missing provider field) sends via Resend SDK."""
    config = {
        "api_key": "encrypted-re_test123",
        "from_email": "Pulse <noreply@pulse.app>",
        "to_email": "admin@example.com",
    }
    with patch("app.services.integrations.email.resend") as mock_resend, \
         patch("app.services.integrations.email.decrypt_api_key", return_value="re_test123"):
        result = send_email(config, "Test Subject", "<h1>Hello</h1>")
        assert result is True
        mock_resend.Emails.send.assert_called_once()


def test_send_email_resend_explicit_provider():
    """Explicit provider=resend routes to Resend."""
    config = {
        "provider": "resend",
        "api_key": "encrypted-re_test123",
        "from_email": "Pulse <noreply@pulse.app>",
        "to_email": "admin@example.com",
    }
    with patch("app.services.integrations.email.resend") as mock_resend, \
         patch("app.services.integrations.email.decrypt_api_key", return_value="re_test123"):
        result = send_email(config, "Test Subject", "<h1>Hello</h1>")
        assert result is True
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_email_service.py -v`
Expected: All 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/unit/test_email_service.py
git commit -m "fix(tests): mock decrypt_api_key in email service tests"
```

---

### Task 3: Fix realtime tests (stale _create_manager mock)

**Files:**
- Rewrite: `backend/tests/unit/test_realtime.py`

**Root cause:** Tests patch `_create_manager` which was removed. The realtime module now uses `_get_sio()` (API process) or `_emit_via_http()` (workers). Tests should verify `emit_to_workspace` dispatches correctly.

- [ ] **Step 1: Rewrite test_realtime.py**

Replace the full content of `backend/tests/unit/test_realtime.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_emit_to_workspace_uses_sio_in_api_process():
    """When _get_sio() returns a server instance, emit directly via Socket.IO."""
    from app.services.realtime import emit_to_workspace

    mock_sio = AsyncMock()
    with patch("app.services.realtime._get_sio", return_value=mock_sio):
        await emit_to_workspace("ws-123", "test:event", {"key": "value"})

    mock_sio.emit.assert_awaited_once_with("test:event", {"key": "value"}, room="ws-123")


@pytest.mark.asyncio
async def test_emit_to_workspace_uses_http_in_worker():
    """When _get_sio() returns None (worker), emit via HTTP endpoint."""
    from app.services.realtime import emit_to_workspace

    with patch("app.services.realtime._get_sio", return_value=None), \
         patch("app.services.realtime._emit_via_http", new_callable=AsyncMock) as mock_http:
        await emit_to_workspace("ws-123", "test:event", {"key": "value"})

    mock_http.assert_awaited_once_with("test:event", {"key": "value"}, "ws-123")


@pytest.mark.asyncio
async def test_emit_to_workspace_swallows_exceptions():
    """emit_to_workspace logs but does not raise on failure."""
    from app.services.realtime import emit_to_workspace

    with patch("app.services.realtime._get_sio", side_effect=Exception("connection lost")):
        # Should not raise
        await emit_to_workspace("ws-123", "test:event", {"data": 1})
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_realtime.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_realtime.py
git commit -m "fix(tests): rewrite realtime tests for new emit architecture"
```

---

### Task 4: Fix emit_task_event tests (stale _create_manager mock)

**Files:**
- Rewrite: `backend/tests/unit/test_emit_task_event.py`

**Root cause:** Same `_create_manager` issue as Task 3. `emit_task_event` now also calls `write_task_state`/`clear_task_state` (Redis) and `_log_task_event` (DB). Tests should mock these and verify the correct event is emitted.

- [ ] **Step 1: Rewrite test_emit_task_event.py**

Replace the full content of `backend/tests/unit/test_emit_task_event.py`:

```python
import uuid

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_emit_task_event_started():
    """emit_task_event emits task:started with correct payload."""
    from app.services.realtime import emit_task_event

    with patch("app.services.realtime.emit_to_workspace", new_callable=AsyncMock) as mock_emit, \
         patch("app.services.realtime.write_task_state", new_callable=AsyncMock), \
         patch("app.services.realtime._log_task_event", new_callable=AsyncMock):
        await emit_task_event(
            workspace_id="ws-abc",
            event_type="started",
            task_name="analyze_conversation",
            task_id="task-123",
            detail="Processing conversation",
        )

    mock_emit.assert_awaited_once_with(
        "ws-abc",
        "task:started",
        {
            "task_name": "analyze_conversation",
            "task_id": "task-123",
            "detail": "Processing conversation",
            "current": None,
            "total": None,
            "error": None,
        },
    )


@pytest.mark.asyncio
async def test_emit_task_event_completed_with_error():
    """emit_task_event emits task:completed with error field."""
    from app.services.realtime import emit_task_event

    with patch("app.services.realtime.emit_to_workspace", new_callable=AsyncMock) as mock_emit, \
         patch("app.services.realtime.clear_task_state", new_callable=AsyncMock), \
         patch("app.services.realtime._log_task_event", new_callable=AsyncMock):
        await emit_task_event(
            workspace_id="ws-abc",
            event_type="completed",
            task_name="export_data",
            task_id="task-456",
            error="Workspace not found",
        )

    mock_emit.assert_awaited_once_with(
        "ws-abc",
        "task:completed",
        {
            "task_name": "export_data",
            "task_id": "task-456",
            "detail": None,
            "current": None,
            "total": None,
            "error": "Workspace not found",
        },
    )


@pytest.mark.asyncio
async def test_emit_task_event_progress():
    """emit_task_event emits task:progress with current/total."""
    from app.services.realtime import emit_task_event

    with patch("app.services.realtime.emit_to_workspace", new_callable=AsyncMock) as mock_emit, \
         patch("app.services.realtime.write_task_state", new_callable=AsyncMock), \
         patch("app.services.realtime._log_task_event", new_callable=AsyncMock):
        await emit_task_event(
            workspace_id="ws-abc",
            event_type="progress",
            task_name="cluster_gaps",
            task_id="task-789",
            current=3,
            total=10,
        )

    mock_emit.assert_awaited_once_with(
        "ws-abc",
        "task:progress",
        {
            "task_name": "cluster_gaps",
            "task_id": "task-789",
            "detail": None,
            "current": 3,
            "total": 10,
            "error": None,
        },
    )


@pytest.mark.asyncio
async def test_emit_task_event_uuid_workspace_id():
    """emit_task_event converts UUID workspace_id to string."""
    from app.services.realtime import emit_task_event

    ws_uuid = uuid.UUID("350863e7-3dc8-430e-bc23-fd41d4499d7b")
    with patch("app.services.realtime.emit_to_workspace", new_callable=AsyncMock) as mock_emit, \
         patch("app.services.realtime.write_task_state", new_callable=AsyncMock), \
         patch("app.services.realtime._log_task_event", new_callable=AsyncMock):
        await emit_task_event(
            workspace_id=ws_uuid,
            event_type="started",
            task_name="export_data",
            task_id="task-1",
        )

    mock_emit.assert_awaited_once()
    call_args = mock_emit.call_args
    assert call_args[0][0] == "350863e7-3dc8-430e-bc23-fd41d4499d7b"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_emit_task_event.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_emit_task_event.py
git commit -m "fix(tests): rewrite emit_task_event tests for new realtime architecture"
```

---

### Task 5: Fix ingest completion check test (missing 5th execute mock + realtime mocks)

**Files:**
- Modify: `backend/tests/unit/test_ingest_completion_check.py:28-33,41-43`

**Root cause:** When the atomic update succeeds, the function now does a 5th `session.execute` (line 144 of source) to get `workspace_id` for the realtime emission. The test only provides 4 side effects, causing `StopAsyncIteration`. The function also calls `write_chatbot_setup_state` and `emit_to_workspace`, which need mocking.

- [ ] **Step 1: Update test_fires_autoconfig_when_all_docs_terminal**

In `backend/tests/unit/test_ingest_completion_check.py`, update the `test_fires_autoconfig_when_all_docs_terminal` method. Add a 5th execute result for the workspace_id lookup, and mock the realtime functions:

```python
    @pytest.mark.asyncio
    async def test_fires_autoconfig_when_all_docs_terminal(self):
        """When all KB docs are indexed/failed, and chatbot is 'crawling',
        the atomic update should succeed and fire the autoconfig task."""
        from app.workers.tasks.ingest_document import _check_and_trigger_autoconfig

        doc_id = uuid.uuid4()
        kb_id = uuid.uuid4()
        chatbot_id = uuid.uuid4()
        workspace_id = uuid.uuid4()

        # Simulate: doc lookup → kb lookup → pending count = 0 → update returns chatbot_id → workspace lookup
        session = AsyncMock()

        doc_row = MagicMock()
        doc_row.knowledge_base_id = kb_id

        kb_row = MagicMock()
        kb_row.chatbot_id = chatbot_id

        workspace_row = MagicMock()
        workspace_row.workspace_id = workspace_id

        # sequence of execute() calls: doc, kb, count, update, workspace
        execute_results = [
            MagicMock(one_or_none=MagicMock(return_value=doc_row)),   # doc lookup
            MagicMock(one_or_none=MagicMock(return_value=kb_row)),    # kb lookup
            MagicMock(scalar_one=MagicMock(return_value=0)),           # pending count = 0
            MagicMock(scalar_one_or_none=MagicMock(return_value=chatbot_id)),  # update wins
            MagicMock(one_or_none=MagicMock(return_value=workspace_row)),  # workspace lookup
        ]
        session.execute = AsyncMock(side_effect=execute_results)
        session.commit = AsyncMock()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workers.tasks.ingest_document.async_session_factory", return_value=mock_session_ctx), \
             patch("app.workers.tasks.ingest_document.engine") as mock_engine, \
             patch("app.workers.tasks.ingest_document.run_autoconfig_for_chatbot") as mock_task, \
             patch("app.workers.tasks.ingest_document.write_chatbot_setup_state", new_callable=AsyncMock), \
             patch("app.workers.tasks.ingest_document.emit_to_workspace", new_callable=AsyncMock):
            mock_engine.dispose = AsyncMock()
            await _check_and_trigger_autoconfig(doc_id)

        mock_task.delay.assert_called_once_with(str(chatbot_id))
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_ingest_completion_check.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_ingest_completion_check.py
git commit -m "fix(tests): add 5th execute mock and realtime mocks to ingest completion test"
```

---

### Task 6: Fix frontend socket tests (Zustand subscribe mock + auth callback + transports)

**Files:**
- Modify: `frontend/src/test/socket.test.ts:23-33,53-55`
- Modify: `frontend/src/test/activity-console.test.ts:24-28`
- Modify: `frontend/src/test/realtime-notifications.test.ts:22-26`

**Root cause:** Three issues across all three test files:
1. `useWorkspaceStore` mock doesn't provide `subscribe()` — the source (line 44 of `socket.ts`) calls `useWorkspaceStore.subscribe((state, prev) => ...)` to watch for workspace changes. Each test file has its own `vi.mock` that needs updating (Vitest mocks are file-scoped).
2. Auth changed from `{ token }` static object to `(cb) => cb({ token })` callback (socket.test.ts only)
3. `transports` changed from `["websocket", "polling"]` to `["polling"]` (socket.test.ts only)

- [ ] **Step 1: Update workspace store mock to include subscribe**

In `frontend/src/test/socket.test.ts`, replace the workspace store mock (lines 29-33):

```typescript
vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: {
    getState: () => ({ currentWorkspace: { id: "ws-123" } }),
    subscribe: vi.fn(() => vi.fn()), // returns unsubscribe function
  },
}));
```

- [ ] **Step 2: Update auth and transports assertions**

Replace the `io` call assertion (lines 53-59) in the first test:

```typescript
    expect(io).toHaveBeenCalledWith("http://localhost:8000", {
      auth: expect.any(Function),
      transports: ["polling"],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    // Verify auth callback provides the token
    const authCallback = (io as ReturnType<typeof vi.fn>).mock.calls[0][1].auth;
    const cbSpy = vi.fn();
    authCallback(cbSpy);
    expect(cbSpy).toHaveBeenCalledWith({ token: "test-token" });
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `docker compose exec frontend npx vitest run src/test/socket.test.ts`
Expected: All 4 tests PASS

- [ ] **Step 4: Add `subscribe` to workspace store mock in activity-console.test.ts**

In `frontend/src/test/activity-console.test.ts`, replace the workspace store mock (lines 24-28):

```typescript
vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: {
    getState: () => ({ currentWorkspace: { id: "ws-123" } }),
    subscribe: vi.fn(() => vi.fn()), // returns unsubscribe function
  },
}));
```

- [ ] **Step 5: Add `subscribe` to workspace store mock in realtime-notifications.test.ts**

In `frontend/src/test/realtime-notifications.test.ts`, replace the workspace store mock (lines 22-26):

```typescript
vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: {
    getState: () => ({ currentWorkspace: { id: "ws-123" } }),
    subscribe: vi.fn(() => vi.fn()), // returns unsubscribe function
  },
}));
```

- [ ] **Step 6: Run all three frontend test files**

Run: `docker compose exec frontend npx vitest run src/test/socket.test.ts src/test/activity-console.test.ts src/test/realtime-notifications.test.ts`
Expected: All tests PASS (socket: 4, activity-console: 9, realtime-notifications: 6 = 19 total)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/test/socket.test.ts frontend/src/test/activity-console.test.ts frontend/src/test/realtime-notifications.test.ts
git commit -m "fix(tests): update socket tests for auth callback, transports, and Zustand subscribe"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full backend unit test suite**

Run: `docker compose exec backend pytest tests/unit/ -v --tb=short`
Expected: 264+ passed, 0 failed, 0 errors

- [ ] **Step 2: Run full frontend test suite**

Run: `docker compose exec frontend npx vitest run`
Expected: All unit tests pass (E2E tests excluded — they need full stack)

- [ ] **Step 3: Commit any remaining adjustments**

If any tests still fail, investigate and fix. Then final commit.
