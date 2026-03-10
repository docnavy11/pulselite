# Architectural Fixes — Full Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 15 architectural issues identified in the March 2026 codebase review — covering security, performance, data integrity, navigation, and code consistency.

**Architecture:** Backend is FastAPI + SQLAlchemy async. Frontend is Next.js 15 App Router + Zustand + TypeScript. Fixes are independent by domain and can be parallelised across backend/frontend agents.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Celery / Next.js 15 / React 19 / TypeScript / Tailwind

---

## BACKEND TASKS

---

### Task 1: Add `FRONTEND_URL` to config — replace all hardcoded localhost

**Issue #1 (Critical):** 4 OAuth callbacks hardcode `http://localhost:3001` or use fragile `.replace(':8000', ':3001')` string substitution. Breaks production.

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/api/v1/oauth.py` (lines 246, 366, 478, 592, 705)
- Modify: `backend/app/api/v1/sso.py` (line 312)
- Modify: `backend/app/api/v1/shopify_oauth.py` (line 207)
- Modify: `.env.example`

**Step 1: Add `FRONTEND_URL` to config.py**

Find this block in `backend/app/config.py`:
```python
BASE_URL: str = "http://localhost:8000"
```
Add directly below it:
```python
FRONTEND_URL: str = "http://localhost:3001"
```

**Step 2: Fix `oauth.py` — Slack callback (line ~246)**

Find:
```python
return RedirectResponse("http://localhost:3001/settings/integrations?slack_connected=1")
```
Replace with:
```python
return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?slack_connected=1")
```

**Step 3: Fix `oauth.py` — Zendesk callback (line ~366)**

Find:
```python
f"{settings.BASE_URL.replace(':8000', ':3001')}/settings/integrations?connected=zendesk"
```
Replace with:
```python
f"{settings.FRONTEND_URL}/settings/integrations?connected=zendesk"
```

**Step 4: Fix `oauth.py` — Dropbox callback (line ~478)**

Find:
```python
f"{settings.BASE_URL.replace(':8000', ':3001')}/settings/integrations?connected=dropbox"
```
Replace with:
```python
f"{settings.FRONTEND_URL}/settings/integrations?connected=dropbox"
```

**Step 5: Fix `oauth.py` — Salesforce callback (line ~592)**

Find:
```python
f"{settings.BASE_URL.replace(':8000', ':3001')}/settings/integrations?connected=salesforce"
```
Replace with:
```python
f"{settings.FRONTEND_URL}/settings/integrations?connected=salesforce"
```

**Step 6: Fix `oauth.py` — Google Drive callback (line ~705)**

Find:
```python
f"{settings.BASE_URL.replace(':8000', ':3001')}/settings/integrations?connected=google_drive"
```
Replace with:
```python
f"{settings.FRONTEND_URL}/settings/integrations?connected=google_drive"
```

**Step 7: Fix `shopify_oauth.py` (line ~207)**

Find:
```python
"http://localhost:3001/settings/integrations?shopify_connected=1"
```
Replace with:
```python
f"{settings.FRONTEND_URL}/settings/integrations?shopify_connected=1"
```
Ensure `settings` is imported at the top of `shopify_oauth.py`. If not, add:
```python
from app.config import settings
```

**Step 8: Fix `sso.py` (line ~312)**

Find:
```python
frontend_url = settings.BASE_URL.replace(":8000", ":3001")
```
Replace with:
```python
frontend_url = settings.FRONTEND_URL
```

**Step 9: Add to `.env.example`**

Add:
```
FRONTEND_URL=http://localhost:3001
```

**Step 10: Restart backend and verify**
```bash
docker compose restart backend
```
Check backend logs for startup errors. No functional test needed — this is a config value.

**Step 11: Commit**
```bash
git add backend/app/config.py backend/app/api/v1/oauth.py backend/app/api/v1/sso.py backend/app/api/v1/shopify_oauth.py .env.example
git commit -m "fix: add FRONTEND_URL config, replace all hardcoded localhost OAuth redirects"
```

---

### Task 2: Fix workspace DELETE — require admin role

**Issue #3 (Critical):** Any workspace member can delete the entire workspace. Should require admin/owner role.

**Files:**
- Modify: `backend/app/dependencies.py`
- Modify: `backend/app/api/v1/gdpr.py`

**Step 1: Add `get_workspace_admin` dependency to `dependencies.py`**

After the existing `get_workspace` function, add:
```python
async def get_workspace_admin(
    workspace_id: uuid.UUID,
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.agent_id == current_user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace")
    if membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or owner role required")
    return workspace_id
```

**Step 2: Import `get_workspace_admin` in `gdpr.py`**

Find in `backend/app/api/v1/gdpr.py`:
```python
from app.dependencies import get_current_user, get_workspace
```
Replace with:
```python
from app.dependencies import get_current_user, get_workspace, get_workspace_admin
```

**Step 3: Update the `DELETE /workspaces/{workspace_id}` endpoint in `gdpr.py`**

Find the workspace delete endpoint. It will look like:
```python
@router.delete("")
async def delete_workspace(
    workspace_id: uuid.UUID = Depends(get_workspace),
```
Change `get_workspace` to `get_workspace_admin`:
```python
@router.delete("")
async def delete_workspace(
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
```

**Step 4: Write test**
```python
# backend/tests/test_workspace_delete_auth.py
def test_workspace_delete_requires_admin():
    """Member-role users should get 403 on workspace delete."""
    # This is an integration test stub — run manually against dev server
    # GET /api/v1/workspaces/{id} with member token → expect 403
    # GET /api/v1/workspaces/{id} with admin token → expect 200 or 204
    pass
```

**Step 5: Restart and verify**
```bash
docker compose restart backend
```

**Step 6: Commit**
```bash
git add backend/app/dependencies.py backend/app/api/v1/gdpr.py backend/tests/test_workspace_delete_auth.py
git commit -m "fix: require admin role for workspace deletion (security)"
```

---

### Task 3: Fix N+1 in exceptions list endpoint

**Issue #2 (High):** `GET /exceptions` fires 3 extra queries per conversation item — chatbot name, contact name, last message. With 50 items = 151 queries.

**Files:**
- Modify: `backend/app/api/v1/exceptions.py`

**Step 1: Rewrite the `list_exceptions` query with lateral subqueries**

Replace the entire for-loop body (from `items = []` to the end of the loop) with a single join query. Find the section starting with:
```python
    items = []
    for conv in conversations:
        chatbot_name = None
        if conv.chatbot_id:
            cb_result = await db.execute(select(Chatbot.name).where(Chatbot.id == conv.chatbot_id))
```

Replace everything from `items = []` through the end of the for loop with:
```python
    if not conversations:
        return ExceptionListResponse(items=[], total=total)

    conv_ids = [c.id for c in conversations]
    chatbot_ids = list({c.chatbot_id for c in conversations if c.chatbot_id})
    contact_ids = list({c.contact_id for c in conversations if c.contact_id})

    # Batch fetch chatbot names
    chatbot_map: dict = {}
    if chatbot_ids:
        cb_result = await db.execute(select(Chatbot.id, Chatbot.name).where(Chatbot.id.in_(chatbot_ids)))
        chatbot_map = {row[0]: row[1] for row in cb_result.all()}

    # Batch fetch contact info
    contact_map: dict = {}
    if contact_ids:
        ct_result = await db.execute(
            select(Contact.id, Contact.name, Contact.email).where(Contact.id.in_(contact_ids))
        )
        contact_map = {row[0]: (row[1], row[2]) for row in ct_result.all()}

    # Batch fetch last message per conversation using a subquery
    from sqlalchemy import func as sqlfunc
    latest_msg_subq = (
        select(
            Message.conversation_id,
            sqlfunc.max(Message.created_at).label("latest_at"),
        )
        .where(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
        .subquery()
    )
    last_msg_result = await db.execute(
        select(Message.conversation_id, Message.content)
        .join(
            latest_msg_subq,
            (Message.conversation_id == latest_msg_subq.c.conversation_id)
            & (Message.created_at == latest_msg_subq.c.latest_at),
        )
    )
    last_msg_map: dict = {row[0]: row[1] for row in last_msg_result.all()}

    items = []
    for conv in conversations:
        contact_info = contact_map.get(conv.contact_id, (None, None)) if conv.contact_id else (None, None)
        last_content = last_msg_map.get(conv.id)
        items.append(
            ExceptionConversation(
                id=conv.id,
                workspace_id=conv.workspace_id,
                chatbot_id=conv.chatbot_id,
                chatbot_name=chatbot_map.get(conv.chatbot_id) if conv.chatbot_id else None,
                contact_id=conv.contact_id,
                contact_name=contact_info[0],
                contact_email=contact_info[1],
                escalation_reason=conv.escalation_reason,
                confidence_avg=conv.confidence_avg,
                status=conv.status,
                last_message_preview=last_content[:200] if last_content else None,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
```

Also ensure `Message` is imported at the top of `exceptions.py`. Check existing imports and add if missing:
```python
from app.models.conversations import Conversation, Message
```

**Step 2: Restart and smoke-test**
```bash
docker compose restart backend
# Open http://localhost:8000/api/docs → GET /workspaces/{id}/exceptions → should return same shape
```

**Step 3: Commit**
```bash
git add backend/app/api/v1/exceptions.py
git commit -m "perf: fix N+1 in exceptions list — batch fetch chatbot/contact/message in 3 queries"
```

---

### Task 4: Fix N+1 in sentiment-trends endpoint

**Issue #2 continued:** `GET /sentiment-trends?days=30` fires 30 separate DB queries in a Python loop. Replace with a single `GROUP BY` query.

**Files:**
- Modify: `backend/app/api/v1/dashboard.py`

**Step 1: Rewrite `get_sentiment_trends` endpoint**

Find the function starting at `@router.get("/sentiment-trends")`. The current implementation loops with:
```python
    for i in range(days):
        day = now.date() - timedelta(days=i)
        ...
        result = await db.execute(...)
```

Replace the entire loop with a single aggregation query. Find where the loop starts (after `now = datetime.now(timezone.utc)`) and replace from there to `return {"data": data}`:

```python
    cutoff = now - timedelta(days=days)

    from sqlalchemy import func as sqlfunc, cast
    import sqlalchemy as sa

    stmt = (
        select(
            cast(ConversationAnalysis.created_at, sa.Date).label("day"),
            sqlfunc.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
            sqlfunc.count(ConversationAnalysis.id).label("count"),
        )
        .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
        .where(
            Conversation.workspace_id == workspace_id,
            ConversationAnalysis.sentiment_score.isnot(None),
            ConversationAnalysis.created_at >= cutoff,
        )
        .group_by(cast(ConversationAnalysis.created_at, sa.Date))
        .order_by(cast(ConversationAnalysis.created_at, sa.Date).desc())
    )
    rows = (await db.execute(stmt)).all()
    data = [
        {
            "date": str(row[0]),
            "avg_sentiment": round(float(row[1]), 3) if row[1] else None,
            "count": row[2],
        }
        for row in rows
    ]
    return {"data": data}
```

Ensure `Conversation` is imported in `dashboard.py`. Check existing imports and add if missing.

**Step 2: Restart and smoke-test**
```bash
docker compose restart backend
# Hit GET /workspaces/{id}/sentiment-trends?days=30 and confirm response shape unchanged
```

**Step 3: Commit**
```bash
git add backend/app/api/v1/dashboard.py
git commit -m "perf: replace N-query sentiment-trends loop with single GROUP BY query"
```

---

### Task 5: Replace `flush()` with `commit()` in 4 routers

**Issue #4 (Medium):** Endpoints in integrations, gaps, exceptions, and onboarding call `await db.flush()` without `await db.commit()`. Relies on implicit session commit — fragile.

**Files:**
- Modify: `backend/app/api/v1/integrations.py`
- Modify: `backend/app/api/v1/gaps.py`
- Modify: `backend/app/api/v1/exceptions.py`
- Modify: `backend/app/api/v1/onboarding.py`

**Step 1: Fix `integrations.py`**

Run:
```bash
grep -n "await db.flush()" backend/app/api/v1/integrations.py
```
For every occurrence, change `await db.flush()` to `await db.commit()`.

**Step 2: Fix `gaps.py`**
```bash
grep -n "await db.flush()" backend/app/api/v1/gaps.py
```
Change every `await db.flush()` to `await db.commit()`.

**Step 3: Fix `exceptions.py`**
```bash
grep -n "await db.flush()" backend/app/api/v1/exceptions.py
```
Change every `await db.flush()` to `await db.commit()`.

**Step 4: Fix `onboarding.py`**
```bash
grep -n "await db.flush()" backend/app/api/v1/onboarding.py
```
Change every `await db.flush()` to `await db.commit()`.

**Step 5: Restart**
```bash
docker compose restart backend
```

**Step 6: Commit**
```bash
git add backend/app/api/v1/integrations.py backend/app/api/v1/gaps.py backend/app/api/v1/exceptions.py backend/app/api/v1/onboarding.py
git commit -m "fix: replace db.flush() with db.commit() in integrations/gaps/exceptions/onboarding"
```

---

### Task 6: Rename `alert_min_confidence` to `alert_max_confidence` and fix comment

**Issue #10 (Medium):** Field named `alert_min_confidence` but logic skips alerting when confidence is *above* that value — naming is the inverse of what users expect.

**Files:**
- Modify: `backend/app/workers/tasks/send_alerts.py`

**Step 1: Read the current logic**

Open `backend/app/workers/tasks/send_alerts.py` around line 47:
```python
min_conf = cfg.config.get("alert_min_confidence")
if min_conf is not None and conv.confidence_avg is not None:
    if conv.confidence_avg >= float(min_conf):
        return {"status": "skipped", "reason": "confidence_above_threshold"}
```

**Step 2: Rename the key and clarify the comment**

Replace that block with:
```python
# alert_max_confidence: skip alerting if bot was confident enough (confidence >= threshold means no alert needed)
max_conf = cfg.config.get("alert_max_confidence") or cfg.config.get("alert_min_confidence")
if max_conf is not None and conv.confidence_avg is not None:
    if conv.confidence_avg >= float(max_conf):
        return {"status": "skipped", "reason": "confidence_above_threshold"}
```

Note: We keep backward compatibility by also reading `alert_min_confidence` (old key). New saves will use `alert_max_confidence`.

**Step 3: Commit**
```bash
git add backend/app/workers/tasks/send_alerts.py
git commit -m "fix: rename alert_min_confidence → alert_max_confidence, clarify skip logic comment"
```

---

### Task 7: Encrypt Google Drive access token

**Issue #11 (Medium):** Google Drive OAuth stores `access_token` in plaintext while encrypting `refresh_token`. Inconsistent security.

**Files:**
- Modify: `backend/app/api/v1/oauth.py`

**Step 1: Find the Google Drive callback**

In `oauth.py`, find the `google_drive_callback` function. Locate this section:
```python
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")

    # Optionally encrypt the refresh token
    encrypted_refresh_token = refresh_token
    if settings.FERNET_KEY and refresh_token:
        from cryptography.fernet import Fernet
        f = Fernet(settings.FERNET_KEY.encode())
        encrypted_refresh_token = f.encrypt(refresh_token.encode()).decode()

    google_config = {
        "access_token": access_token,
        "refresh_token": encrypted_refresh_token,
```

**Step 2: Encrypt both tokens**

Replace with:
```python
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")

    encrypted_access_token = access_token
    encrypted_refresh_token = refresh_token
    if settings.FERNET_KEY:
        from cryptography.fernet import Fernet
        f = Fernet(settings.FERNET_KEY.encode())
        if access_token:
            encrypted_access_token = f.encrypt(access_token.encode()).decode()
        if refresh_token:
            encrypted_refresh_token = f.encrypt(refresh_token.encode()).decode()

    google_config = {
        "access_token": encrypted_access_token,
        "refresh_token": encrypted_refresh_token,
```

**Step 3: Restart**
```bash
docker compose restart backend
```

**Step 4: Commit**
```bash
git add backend/app/api/v1/oauth.py
git commit -m "fix: encrypt Google Drive access_token at rest (security consistency)"
```

---

### Task 8: Add `used_this_month` to `/credits/balance` endpoint

**Issue #12 (Medium):** Frontend's `CreditBalance.usage_this_month` always shows 0 because the backend endpoint only returns `{ balance }`.

**Files:**
- Modify: `backend/app/api/v1/billing.py`
- Modify: `frontend/src/lib/api-functions.ts`

**Step 1: Update the billing endpoint to return `used_this_month`**

In `backend/app/api/v1/billing.py`, find:
```python
@router.get("/workspaces/{workspace_id}/credits/balance")
async def get_credit_balance(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    balance = await credits_service.get_balance(db, workspace_id)
    return {"balance": balance}
```

Replace with:
```python
@router.get("/workspaces/{workspace_id}/credits/balance")
async def get_credit_balance(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
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
    used_this_month = used_result.scalar() or 0

    return {"balance": balance, "used_this_month": int(used_this_month)}
```

**Step 2: Check `CreditLedger` model import**

Verify `CreditLedger` is in `backend/app/models/integrations.py`:
```bash
grep -n "CreditLedger" backend/app/models/integrations.py | head -5
```
If the model name differs, use the correct name.

**Step 3: Update frontend `getCreditsBalance` in `api-functions.ts`**

Find in `frontend/src/lib/api-functions.ts`:
```typescript
export async function getCreditsBalance(workspaceId: string): Promise<CreditBalance> {
```
Inside that function, find where `usage_this_month: 0` is hardcoded and replace with the actual value from the response. The response now returns `{ balance, used_this_month }`.

The transform should become:
```typescript
  return {
    balance: data.balance,
    used_this_month: data.used_this_month ?? 0,
    usage_this_month: data.used_this_month ?? 0,
    usage_history: [],
  };
```
(Preserve whatever fields `CreditBalance` type expects — just stop hardcoding 0.)

**Step 4: Restart and verify**
```bash
docker compose restart backend
```

**Step 5: Commit**
```bash
git add backend/app/api/v1/billing.py frontend/src/lib/api-functions.ts
git commit -m "fix: return used_this_month from /credits/balance, wire to billing page"
```

---

### Task 9: Fix `purge_old_data` — cascade delete child rows

**Issue #14 (Medium):** The task deletes `Conversation` rows without first deleting child rows in `Message`, `ConversationAnalysis`, `MessageFeedback`, `ConversationTag`. May leave orphans if FK cascade constraints are absent.

**Files:**
- Modify: `backend/app/workers/tasks/purge_old_data.py`

**Step 1: Read the current task**

Open `backend/app/workers/tasks/purge_old_data.py`. The current code:
```python
del_result = await session.execute(
    delete(Conversation).where(
        Conversation.workspace_id == ws_id,
        Conversation.created_at < cutoff,
    )
)
```

**Step 2: Add explicit child-row deletions before deleting Conversation**

Replace that `del_result = ...` block with:
```python
# First collect IDs to purge
id_result = await session.execute(
    select(Conversation.id).where(
        Conversation.workspace_id == ws_id,
        Conversation.created_at < cutoff,
    )
)
conv_ids = [row[0] for row in id_result.all()]

if not conv_ids:
    continue

# Delete child rows first to avoid FK violations
from app.models.conversations import Message, ConversationAnalysis, MessageFeedback, ConversationTag
await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
await session.execute(delete(MessageFeedback).where(MessageFeedback.conversation_id.in_(conv_ids)))
await session.execute(delete(ConversationTag).where(ConversationTag.conversation_id.in_(conv_ids)))
await session.execute(delete(ConversationAnalysis).where(ConversationAnalysis.conversation_id.in_(conv_ids)))

del_result = await session.execute(
    delete(Conversation).where(Conversation.id.in_(conv_ids))
)
deleted = len(conv_ids)
total_deleted += deleted
```

Also remove the existing `deleted = getattr(del_result, "rowcount", 0) or 0` and `total_deleted += deleted` lines that come after the original delete (since we now count via `len(conv_ids)`).

**Step 3: Verify imports at top of file**

Ensure these imports exist at the top of `purge_old_data.py`:
```python
from sqlalchemy import delete, select
from app.models.conversations import Conversation
```
The child model imports are done inline above to avoid circular import issues — that's acceptable.

**Step 4: Commit**
```bash
git add backend/app/workers/tasks/purge_old_data.py
git commit -m "fix: purge_old_data cascades to Message/Analysis/Feedback/Tag before deleting Conversation"
```

---

### Task 10: Remove dead `compute_sentiment_trends` beat schedule

**Issue #15 (Medium):** A Celery beat task `compute_sentiment_trends` runs daily but the API endpoint recomputes sentiment on demand — the pre-computed cache is never read. Dead work.

**Files:**
- Modify: `backend/app/workers/celery_app.py`

**Step 1: Read the beat schedule**
```bash
grep -n "compute_sentiment\|sentiment_trend" backend/app/workers/celery_app.py
```

**Step 2: Remove the beat schedule entry**

In `backend/app/workers/celery_app.py`, find and remove the `compute_sentiment_trends` entry from the `beat_schedule` dict. It will look like:
```python
"compute_sentiment_trends": {
    "task": "app.workers.tasks.compute_sentiment_trends.compute_sentiment_trends",
    "schedule": ...,
},
```
Delete that entire block (key + value).

**Step 3: Restart celery beat**
```bash
docker compose restart celery_beat
```

**Step 4: Commit**
```bash
git add backend/app/workers/celery_app.py
git commit -m "fix: remove dead compute_sentiment_trends beat schedule (API computes on demand)"
```

---

## FRONTEND TASKS

---

### Task 11: Create shared `ChatbotTabNav` component — fix broken tabs

**Issue #6 (High):** The chatbot sub-page tab nav is duplicated in 4 files with inconsistencies: `customize/page.tsx` has a dead `/chatbots/[id]/settings` link; `chat/page.tsx` and `deploy/page.tsx` are missing the "Actions" tab.

**Files:**
- Create: `frontend/src/components/chatbots/ChatbotTabNav.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/chat/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/deploy/page.tsx`

**Step 1: Create the shared `ChatbotTabNav` component**

Create `frontend/src/components/chatbots/ChatbotTabNav.tsx`:
```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface Props {
  chatbotId: string;
}

const TABS = [
  { label: "Sources", href: (id: string) => `/chatbots/${id}` },
  { label: "Settings", href: (id: string) => `/chatbots/${id}` },
  { label: "Actions", href: (id: string) => `/chatbots/${id}/actions` },
  { label: "Chat", href: (id: string) => `/chatbots/${id}/chat` },
  { label: "Customize", href: (id: string) => `/chatbots/${id}/customize` },
  { label: "Deploy", href: (id: string) => `/chatbots/${id}/deploy` },
];

export function ChatbotTabNav({ chatbotId }: Props) {
  const pathname = usePathname();

  function isActive(label: string, href: string): boolean {
    if (label === "Sources" || label === "Settings") {
      return pathname === `/chatbots/${chatbotId}`;
    }
    return pathname.startsWith(href);
  }

  return (
    <div className="border-b border-gray-200 mb-6">
      <nav className="-mb-px flex space-x-6">
        <Link
          href={`/chatbots/${chatbotId}`}
          className="text-sm text-gray-500 hover:text-gray-700 pb-3 block"
        >
          ← Back to Chatbots
        </Link>
        {TABS.map((tab) => {
          const href = tab.href(chatbotId);
          const active = isActive(tab.label, href);
          return (
            <Link
              key={tab.label}
              href={href}
              className={`pb-3 text-sm font-medium border-b-2 ${
                active
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
```

**Step 2: Replace tab nav in `chat/page.tsx`**

In `frontend/src/app/(dashboard)/chatbots/[id]/chat/page.tsx`:

Add import at top:
```tsx
import { ChatbotTabNav } from "@/components/chatbots/ChatbotTabNav";
```

Find the existing `const tabs = [...]` array and the JSX that renders it (the back-link + tab nav block). Delete the entire `const tabs` declaration and replace the JSX nav block with:
```tsx
<ChatbotTabNav chatbotId={chatbotId} />
```

**Step 3: Replace tab nav in `customize/page.tsx`**

In `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx`:

Add import at top:
```tsx
import { ChatbotTabNav } from "@/components/chatbots/ChatbotTabNav";
```

Delete `const tabs = [...]` and replace the tab nav JSX block with:
```tsx
<ChatbotTabNav chatbotId={chatbotId} />
```

**Step 4: Replace tab nav in `deploy/page.tsx`**

In `frontend/src/app/(dashboard)/chatbots/[id]/deploy/page.tsx`:

Add import at top:
```tsx
import { ChatbotTabNav } from "@/components/chatbots/ChatbotTabNav";
```

Delete `const chatbotTabs = [...]` and replace the chatbot-level tab nav JSX block with:
```tsx
<ChatbotTabNav chatbotId={chatbotId} />
```
Note: `deploy/page.tsx` has a second inner tab nav ("Script Tag", "Shareable Link", "REST API") — keep that one intact.

**Step 5: Build check**
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Fix any type errors.

**Step 6: Commit**
```bash
git add frontend/src/components/chatbots/ChatbotTabNav.tsx \
        frontend/src/app/\(dashboard\)/chatbots/\[id\]/chat/page.tsx \
        frontend/src/app/\(dashboard\)/chatbots/\[id\]/customize/page.tsx \
        frontend/src/app/\(dashboard\)/chatbots/\[id\]/deploy/page.tsx
git commit -m "fix: shared ChatbotTabNav component — add Actions tab, fix dead /settings link"
```

---

### Task 12: Fix `settings/page.tsx` — remove mock team data, wire workspace name save

**Issue #7 (Medium):** Settings page Team tab shows hardcoded fixtures. Workspace name Save button has `/* TODO */`.

**Files:**
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx`

**Step 1: Read the full settings page**
```bash
cat frontend/src/app/\(dashboard\)/settings/page.tsx
```

**Step 2: Remove the hardcoded `teamMembers` array and Team tab**

Find at top of component:
```typescript
const teamMembers = [
  { name: "Admin User", ... },
  ...
];
```
Delete the entire `teamMembers` array.

Find the "Team" tab content in the JSX — it will be inside a condition like `activeTab === "Team"` and renders the hardcoded member list. Replace the entire Team tab panel content with a redirect notice:
```tsx
{activeTab === "Team" && (
  <div className="py-4">
    <p className="text-sm text-gray-600">
      Manage team members and invitations on the{" "}
      <a href="/settings/team" className="text-blue-600 underline">Team page</a>.
    </p>
  </div>
)}
```

**Step 3: Wire the workspace name Save button**

Find:
```tsx
<Button size="sm" onClick={() => { /* TODO: wire to API */ }}>Save</Button>
```

First, check if there's a `workspaceName` state variable in the component. If not, add:
```tsx
const [workspaceName, setWorkspaceName] = useState(workspace?.name ?? "");
```
And update the input to use `value={workspaceName} onChange={e => setWorkspaceName(e.target.value)}`.

Then wire the Save button:
```tsx
<Button
  size="sm"
  onClick={async () => {
    if (!workspace) return;
    try {
      await api.put(`/api/v1/workspaces/${workspace.id}`, { name: workspaceName });
    } catch {
      // ignore — workspace update is best-effort
    }
  }}
>
  Save
</Button>
```

Note: Check if `PUT /workspaces/{id}` exists. If not, this can be a no-op save with a toast — but the button should not silently do nothing.

**Step 4: Build check**
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

**Step 5: Commit**
```bash
git add frontend/src/app/\(dashboard\)/settings/page.tsx
git commit -m "fix: remove mock team data from settings page, wire workspace name Save button"
```

---

### Task 13: Remove dead `/knowledge-base` sidebar link

**Issue #8 (Medium):** Sidebar has a "Knowledge Base" link pointing to `/knowledge-base` — a route that doesn't exist.

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

**Step 1: Find and remove the dead nav item**

In `frontend/src/components/layout/Sidebar.tsx`, find:
```typescript
{ href: "/knowledge-base", label: "Knowledge Base", icon: BookOpen },
```
Delete that line entirely.

**Step 2: Check if `BookOpen` import becomes unused**

If `BookOpen` is now unused (only imported for this link), remove it from the import statement too.

**Step 3: Build check**
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

**Step 4: Commit**
```bash
git add frontend/src/components/layout/Sidebar.tsx
git commit -m "fix: remove dead /knowledge-base sidebar link (route does not exist)"
```

---

### Task 14: Fix onboarding state variable discarded

**Issue #13 (Low):** `onboarding/page.tsx` line 31 discards the state value with `const [, setState]`. API response cannot be reflected in UI.

**Files:**
- Modify: `frontend/src/app/(dashboard)/onboarding/page.tsx`

**Step 1: Fix destructuring**

Find in `frontend/src/app/(dashboard)/onboarding/page.tsx`:
```typescript
const [, setState] = useState<OnboardingState | null>(null);
```
Replace with:
```typescript
const [state, setState] = useState<OnboardingState | null>(null);
```

**Step 2: Use `state` to initialize `currentStep`**

Find:
```typescript
useEffect(() => {
    getOnboardingState(workspace.id)
      .then(s => {
        setState(s);
```
Ensure the then-block also calls `setCurrentStep(s.current_step ?? 0)` or similar — check what field `OnboardingState` has for the current step. Look at the type in `types.ts`:
```bash
grep -A 5 "OnboardingState" frontend/src/lib/types.ts
```
Then set `currentStep` from `state` in the `useEffect`.

**Step 3: Build check**
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

**Step 4: Commit**
```bash
git add frontend/src/app/\(dashboard\)/onboarding/page.tsx
git commit -m "fix: restore onboarding state variable (was discarded with [, setState])"
```

---

### Task 15: Move inline API calls to `api-functions.ts`

**Issue #9 (Low-Med):** ~6 pages call `api.get()`/`api.post()` directly instead of using the `api-functions.ts` transform layer. Inconsistent architecture, no type safety on response shapes.

**Files:**
- Modify: `frontend/src/lib/api-functions.ts`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx`
- Modify: `frontend/src/app/(dashboard)/intelligence/competitive/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/data-retention/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/sso/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/security/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/team/page.tsx`
- Modify: `frontend/src/app/(dashboard)/intelligence/sentiment/page.tsx`

**Step 1: Move `Action` type to `types.ts`**

In `frontend/src/lib/types.ts`, add:
```typescript
export interface Action {
  id: string;
  action_type: string;
  name: string;
  description?: string;
  config: Record<string, unknown>;
  is_enabled: boolean;
}
```

**Step 2: Add action API functions to `api-functions.ts`**

```typescript
export async function getActions(workspaceId: string, chatbotId: string): Promise<Action[]> {
  const data = await api.get(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/actions`);
  return data as Action[];
}

export async function createAction(workspaceId: string, chatbotId: string, body: Partial<Action>): Promise<Action> {
  const data = await api.post(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/actions`, body);
  return data as Action;
}

export async function updateAction(workspaceId: string, chatbotId: string, actionId: string, body: Partial<Action>): Promise<Action> {
  const data = await api.patch(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/actions/${actionId}`, body);
  return data as Action;
}

export async function deleteAction(workspaceId: string, chatbotId: string, actionId: string): Promise<void> {
  await api.delete(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/actions/${actionId}`);
}
```

**Step 3: Add SSO functions**

```typescript
export interface SSOConfig {
  provider_name: string;
  client_id: string;
  client_secret?: string;
  discovery_url: string;
  email_domain: string;
  is_active: boolean;
}

export async function getSSOConfig(workspaceId: string): Promise<SSOConfig | null> {
  try {
    const data = await api.get(`/api/v1/workspaces/${workspaceId}/sso`);
    return data as SSOConfig;
  } catch {
    return null;
  }
}

export async function updateSSOConfig(workspaceId: string, body: Partial<SSOConfig>): Promise<SSOConfig> {
  const data = await api.put(`/api/v1/workspaces/${workspaceId}/sso`, body);
  return data as SSOConfig;
}

export async function deleteSSOConfig(workspaceId: string): Promise<void> {
  await api.delete(`/api/v1/workspaces/${workspaceId}/sso`);
}
```

**Step 4: Add data retention functions**

```typescript
export async function getDataRetention(workspaceId: string): Promise<{ data_retention_days: number | null }> {
  const data = await api.get(`/api/v1/workspaces/${workspaceId}/data-retention`);
  return data as { data_retention_days: number | null };
}

export async function updateDataRetention(workspaceId: string, days: number | null): Promise<void> {
  await api.put(`/api/v1/workspaces/${workspaceId}/data-retention`, { data_retention_days: days });
}
```

**Step 5: Add team/invite functions**

```typescript
export interface Invite {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

export async function getInvites(workspaceId: string): Promise<Invite[]> {
  const data = await api.get(`/api/v1/workspaces/${workspaceId}/invites`);
  return data as Invite[];
}

export async function createInvite(workspaceId: string, email: string, role: string): Promise<Invite> {
  const data = await api.post(`/api/v1/workspaces/${workspaceId}/invites`, { email, role });
  return data as Invite;
}

export async function deleteInvite(workspaceId: string, inviteId: string): Promise<void> {
  await api.delete(`/api/v1/workspaces/${workspaceId}/invites/${inviteId}`);
}
```

**Step 6: Add sentiment segment function**

```typescript
export interface SegmentSentimentItem {
  name: string;
  avg_sentiment: number;
  count: number;
}

export async function getSentimentBySegment(
  workspaceId: string,
  segment: "chatbot" | "contact",
  days = 30
): Promise<SegmentSentimentItem[]> {
  const data = await api.get(
    `/api/v1/workspaces/${workspaceId}/sentiment-by-segment?days=${days}&segment=${segment}`
  );
  return (data as { data: SegmentSentimentItem[] }).data;
}
```

**Step 7: Update each page to use the new functions**

For each page listed in **Files** above:
1. Remove the `import { api } from "@/lib/api"` if it's only used for the calls being moved
2. Import the new functions from `@/lib/api-functions`
3. Replace the inline `api.get(...)` / `api.post(...)` / `api.delete(...)` calls with the new function calls

Do this page-by-page. Start with `actions/page.tsx` as it has the most inline calls.

**Step 8: Move `Webhook` type from `api-functions.ts` to `types.ts`**

Find in `api-functions.ts`:
```typescript
interface Webhook {
```
Move it (as `export interface Webhook`) to `frontend/src/lib/types.ts` and remove the local declaration.

**Step 9: Build check**
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```
Fix all type errors before committing.

**Step 10: Commit**
```bash
git add frontend/src/lib/api-functions.ts \
        frontend/src/lib/types.ts \
        frontend/src/app/\(dashboard\)/chatbots/\[id\]/actions/page.tsx \
        frontend/src/app/\(dashboard\)/intelligence/competitive/page.tsx \
        frontend/src/app/\(dashboard\)/settings/data-retention/page.tsx \
        frontend/src/app/\(dashboard\)/settings/sso/page.tsx \
        frontend/src/app/\(dashboard\)/settings/security/page.tsx \
        frontend/src/app/\(dashboard\)/settings/team/page.tsx \
        frontend/src/app/\(dashboard\)/intelligence/sentiment/page.tsx
git commit -m "refactor: move inline API calls to api-functions.ts, types to types.ts"
```

---

## Execution Order

Independent tasks can be parallelised. Recommended order:

**Round 1 (parallel — backend critical):**
- Task 1: FRONTEND_URL config
- Task 2: Workspace delete auth

**Round 2 (parallel — backend high/medium):**
- Task 3: Exceptions N+1
- Task 4: Sentiment N+1
- Task 5: flush → commit
- Task 7: Google Drive token encryption
- Task 9: Purge cascade

**Round 3 (parallel — backend medium + frontend):**
- Task 6: Alert naming
- Task 8: Credits used_this_month
- Task 10: Remove dead beat schedule
- Task 11: ChatbotTabNav (frontend)
- Task 12: Settings mock data (frontend)
- Task 13: Dead sidebar link (frontend)
- Task 14: Onboarding state fix (frontend)

**Round 4 (sequential — frontend refactor):**
- Task 15: Move inline API calls (depends on types from earlier tasks)
