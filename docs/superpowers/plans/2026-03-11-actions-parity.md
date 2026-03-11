# Actions Parity (Chatbase+) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring PulseLite actions to full Chatbase parity and beyond: lead webhook notifications with HMAC signing, inline Calendly/Cal.com embeds, client-side `registerTools` API, conversational parameter collection via LLM function calling, and Stripe/Salesforce action types.

**Architecture:** Four phases delivered in order. Chunks 1–3 are independent and can run in parallel. Chunk 4 (function calling) is the largest architectural change — it adds a pre-response tool-detection step to the RAG engine so actions with declared parameters are collected conversationally before the final answer is streamed. Chunk 5 adds two more action types that reuse existing workspace integrations.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, OpenRouter (OpenAI-compatible tool calling), TypeScript, Rollup widget build, `hmac` stdlib (Python), Calendly/Cal.com embed scripts.

**Key files to understand before starting:**
- `backend/app/services/rag/engine.py` — RAG pipeline entry point; Chunk 4 modifies this
- `backend/app/services/rag/generator.py` — calls LLM; Chunk 4 adds tool-calling path here
- `backend/app/services/action_executor.py` — executes triggered actions; Chunks 1 + 5 modify this
- `backend/app/api/v1/public_chat.py` — widget SSE endpoint + lead capture; Chunk 1 modifies this
- `widget/src/widget.ts` — widget logic; Chunks 2 + 3 modify this
- `widget/src/api.ts` — SSE stream parser; Chunk 3 modifies this
- `backend/app/schemas/actions.py` — Pydantic action schemas; Chunks 3 + 4 + 5 modify this

---

## File Map

| File | Action | Responsible for |
|---|---|---|
| `backend/app/api/v1/public_chat.py` | Modify | Fire lead notification webhooks after contact save |
| `backend/app/services/action_executor.py` | Modify | HMAC signing + Stripe + Salesforce handlers |
| `backend/app/schemas/actions.py` | Modify | Add `custom_tool`, `stripe_lookup`, `salesforce_ticket` types + `parameters` field |
| `backend/app/models/actions.py` | Modify | Add `parameters` mapped column |
| `backend/alembic/versions/2026_03_11_action_parameters.py` | **Create** | Add `parameters` JSONB column to `chatbot_actions` |
| `backend/app/services/llm/base.py` | Modify | Add `generate_with_tools` abstract method |
| `backend/app/services/llm/openrouter_client.py` | Modify | Implement `generate_with_tools` |
| `backend/app/services/action_tools.py` | **Create** | Build OpenAI tool definitions from `ChatbotAction` list |
| `backend/app/services/rag/engine.py` | Modify | Pre-response tool detection step |
| `backend/app/services/rag/generator.py` | Modify | `stream_response_with_tool_result` variant |
| `backend/tests/unit/test_action_executor.py` | Modify | HMAC signing tests |
| `backend/tests/unit/test_action_tools.py` | **Create** | Tool definition building tests |
| `widget/src/widget.ts` | Modify | Inline embed cards, `registerTool`, `custom_tool` handler |
| `widget/src/ui/styles.ts` | Modify | Embed card styles |
| `widget/src/index.ts` | Modify | Expose public `registerTool` API |
| `frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx` | Modify | Parameter editor UI in add/edit form |
| `frontend/src/lib/types.ts` | Modify | Add `parameters` to `Action`/`ActionCreate`/`ActionUpdate` |

---

## Chunk 1: Lead Webhook Notification + HMAC Signing

**What this delivers:** When a visitor submits the lead capture form, every enabled webhook/slack action on that chatbot fires with the lead data (name, email, phone, conversationId). All webhook payloads include an `X-PulseLite-Signature` HMAC-SHA256 header so receiving servers can verify authenticity.

### Task 1: HMAC signing in action executor

**Files:**
- Modify: `backend/app/services/action_executor.py`
- Modify: `backend/tests/unit/test_action_executor.py`

- [ ] **Step 1: Write failing test for HMAC signing**

```python
# In backend/tests/unit/test_action_executor.py — add to existing file
import hashlib
import hmac
import json
from app.services.action_executor import compute_signature


def test_compute_signature_deterministic():
    secret = "mysecret"
    payload = {"event": "lead.submit", "email": "user@example.com"}
    sig1 = compute_signature(secret, payload)
    sig2 = compute_signature(secret, payload)
    assert sig1 == sig2
    assert len(sig1) == 64  # SHA-256 hex digest


def test_compute_signature_differs_with_different_secret():
    payload = {"event": "test"}
    assert compute_signature("secret1", payload) != compute_signature("secret2", payload)
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
docker compose exec backend pytest tests/unit/test_action_executor.py::test_compute_signature_deterministic -v
```

Expected: `ImportError: cannot import name 'compute_signature'`

- [ ] **Step 3: Add `compute_signature` and wire it into `_execute_webhook`**

In `backend/app/services/action_executor.py`, add after the imports:

```python
import hashlib
import hmac as hmac_lib
import json


def compute_signature(secret: str, payload: dict) -> str:
    """Return hex SHA-256 HMAC of JSON-serialised payload."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac_lib.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
```

Then in `_execute_webhook`, add signature header when a secret is configured:

```python
async def _execute_webhook(action: ChatbotAction, context: dict[str, Any]) -> str:
    url = action.config.get("url", "").strip()
    if not url:
        return "error:no_url"
    method = action.config.get("method", "POST").upper()
    payload = {"action": action.name, "action_id": str(action.id), **context}

    headers: dict[str, str] = {"Content-Type": "application/json"}
    secret = action.config.get("secret", "").strip()
    if secret:
        headers["X-PulseLite-Signature"] = f"sha256={compute_signature(secret, payload)}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "POST":
                r = await client.post(url, json=payload, headers=headers)
            else:
                r = await client.get(url, params={k: str(v) for k, v in payload.items()})
        return "ok" if r.is_success else f"error:{r.status_code}"
    except Exception as exc:
        logger.warning(f"Webhook action {action.id} failed: {exc}")
        return "error:request_failed"
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker compose exec backend pytest tests/unit/test_action_executor.py -v
```

---

### Task 2: Lead notification on form submit

**Files:**
- Modify: `backend/app/api/v1/public_chat.py`

The `capture_lead` endpoint currently saves a Contact then returns. After saving, it should look up any enabled `collect_lead` or `webhook` actions and fire them with the lead data.

- [ ] **Step 1: Update `capture_lead` to fire notifications**

In `backend/app/api/v1/public_chat.py`, update the `capture_lead` function:

```python
@router.post("/public/chat/lead")
@limiter.limit("10/minute")
async def capture_lead(
    request: Request,
    body: LeadCapture,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Chatbot).where(Chatbot.id == body.chatbot_id, Chatbot.is_active == True))  # noqa: E712
    chatbot = result.scalar_one_or_none()
    if chatbot is None:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    if body.email:
        existing = await db.execute(
            select(Contact).where(
                Contact.workspace_id == chatbot.workspace_id,
                Contact.email == body.email,
            )
        )
        if existing.scalar_one_or_none():
            # Still fire notification even for existing contact
            await _fire_lead_notifications(db, chatbot, body)
            return {"status": "existing"}

    contact = Contact(
        workspace_id=chatbot.workspace_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        contact_type="lead",
        external_id=body.session_id,
    )
    db.add(contact)
    await db.commit()

    await _fire_lead_notifications(db, chatbot, body)
    return {"status": "created"}


async def _fire_lead_notifications(db, chatbot, body: "LeadCapture") -> None:
    """Fire webhook/slack actions with lead data after form submission."""
    import asyncio
    from app.services.action_executor import execute_action, _get_workspace_slack_webhook
    from app.services.action_service import list_enabled_actions
    from app.models.actions import ActionEvent
    import uuid as _uuid

    actions = await list_enabled_actions(db, chatbot.workspace_id, chatbot.id)
    notifiable = [a for a in actions if a.action_type in ("webhook", "slack_message")]
    if not notifiable:
        return

    slack_webhook = await _get_workspace_slack_webhook(db, chatbot.workspace_id)
    context = {
        "event": "lead.submit",
        "name": body.name or "",
        "email": body.email or "",
        "phone": body.phone or "",
        "session_id": body.session_id,
    }

    async def _run():
        for action in notifiable:
            status, _ = await execute_action(action, context, slack_webhook)
            event = ActionEvent(
                id=_uuid.uuid4(),
                workspace_id=chatbot.workspace_id,
                chatbot_id=chatbot.id,
                conversation_id=None,
                action_id=action.id,
                action_type=action.action_type,
                payload=context,
                status=status,
            )
            db.add(event)
        await db.commit()

    asyncio.create_task(_run())
```

- [ ] **Step 2: Restart backend + manual test**

```bash
docker compose restart backend
```

Create a webhook action on the dev chatbot pointing to https://webhook.site (get a free URL there). Open widget, trigger the lead form, submit it. Confirm the webhook fires with the lead data.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/action_executor.py \
        backend/app/api/v1/public_chat.py \
        backend/tests/unit/test_action_executor.py
git commit -m "feat: HMAC signing on webhooks + lead notification on form submit"
```

---

## Chunk 2: Inline Calendly + Cal.com Embed

**What this delivers:** Instead of a plain link button, Calendly/Cal.com actions show an expandable card inside the chat with a genuine inline booking widget. Clicking "Show calendar" loads the embed in-place inside the chat window.

### Task 3: Inline embed widget in chat

**Files:**
- Modify: `widget/src/widget.ts`
- Modify: `widget/src/ui/styles.ts`

The widget chat window is 520px tall. A full Calendly inline embed is 700px. Solution: render an expandable container (collapsed by default showing a booking card, expanded to a 480px iframe that scrolls independently).

- [ ] **Step 1: Replace `showActionButton` for booking types with `showBookingCard`**

In `widget/src/widget.ts`, update `onAction` handler:

```typescript
} else if (actionData.type === "calendly") {
  this.showBookingCard(
    cfg.label || "Book a meeting",
    cfg.calendly_url || "",
    "calendly"
  );
} else if (actionData.type === "calcom") {
  this.showBookingCard(
    cfg.label || "Book a meeting",
    cfg.calcom_url || "",
    "calcom"
  );
```

- [ ] **Step 2: Add `showBookingCard` method**

```typescript
private showBookingCard(label: string, url: string, provider: "calendly" | "calcom"): void {
  if (!url) return;

  const card = document.createElement("div");
  card.className = "pulse-booking-card";

  const header = document.createElement("div");
  header.className = "pulse-booking-header";

  const icon = document.createElement("span");
  icon.className = "pulse-booking-icon";
  icon.textContent = "📅";

  const title = document.createElement("span");
  title.className = "pulse-booking-title";
  title.textContent = label;

  const toggle = document.createElement("button");
  toggle.className = "pulse-booking-toggle";
  toggle.textContent = "Show calendar";

  header.appendChild(icon);
  header.appendChild(title);
  header.appendChild(toggle);
  card.appendChild(header);

  const embedContainer = document.createElement("div");
  embedContainer.className = "pulse-booking-embed";
  embedContainer.style.display = "none";
  card.appendChild(embedContainer);

  let loaded = false;
  toggle.addEventListener("click", () => {
    const isOpen = embedContainer.style.display !== "none";
    if (isOpen) {
      embedContainer.style.display = "none";
      toggle.textContent = "Show calendar";
    } else {
      embedContainer.style.display = "block";
      toggle.textContent = "Hide calendar";
      if (!loaded) {
        loaded = true;
        this._loadBookingEmbed(embedContainer, url, provider);
      }
      this.scrollToBottom();
    }
  });

  this.chatWindow.messagesContainer.appendChild(card);
  this.scrollToBottom();
}

private _loadBookingEmbed(container: HTMLElement, url: string, provider: "calendly" | "calcom"): void {
  if (provider === "calendly") {
    // Calendly inline embed via iframe (no external script needed)
    const embedUrl = url.includes("?")
      ? `${url}&embed_domain=${location.hostname}&embed_type=Inline`
      : `${url}?embed_domain=${location.hostname}&embed_type=Inline`;
    const iframe = document.createElement("iframe");
    iframe.src = embedUrl;
    iframe.width = "100%";
    iframe.height = "460";
    iframe.frameBorder = "0";
    iframe.style.borderRadius = "8px";
    container.appendChild(iframe);
  } else {
    // Cal.com iframe embed
    const embedUrl = url.includes("?") ? `${url}&embed=true` : `${url}?embed=true`;
    const iframe = document.createElement("iframe");
    iframe.src = embedUrl;
    iframe.width = "100%";
    iframe.height = "460";
    iframe.frameBorder = "0";
    iframe.style.borderRadius = "8px";
    container.appendChild(iframe);
  }
}
```

- [ ] **Step 3: Add booking card CSS to `styles.ts`**

Add inside `getStyles` before the closing backtick:

```css
.pulse-booking-card {
  margin: 4px 0;
  border: 1.5px solid var(--pulse-border);
  border-radius: 12px;
  overflow: hidden;
  background: var(--pulse-bg);
}
.pulse-booking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
}
.pulse-booking-icon { font-size: 16px; flex-shrink: 0; }
.pulse-booking-title {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--pulse-text);
}
.pulse-booking-toggle {
  background: var(--pulse-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity 0.15s;
}
.pulse-booking-toggle:hover { opacity: 0.85; }
.pulse-booking-embed {
  border-top: 1px solid var(--pulse-border);
  overflow: hidden;
}
.pulse-booking-embed iframe {
  display: block;
  border: none;
}
```

- [ ] **Step 4: Build widget and verify**

```bash
cd /Users/yvanveldeman/dev/pulselite/widget && npm run build
```

Expected: `created dist/widget.js`

Add a Calendly action on the dev chatbot, trigger it in the test chat page, confirm the booking card appears with expand/collapse.

- [ ] **Step 5: Commit**

```bash
git add widget/src/widget.ts widget/src/ui/styles.ts widget/dist/widget.js
git commit -m "feat: inline Calendly/Cal.com booking cards in chat widget"
```

---

## Chunk 3: Client-side Custom Actions (registerTools)

**What this delivers:** Page owners can register JavaScript functions that the AI triggers by name. This enables DOM manipulation, cart actions, navigation — anything JS can do — without needing a server.

**How it works:**
1. Page embeds widget and calls `window.PulseWidget("registerTool", { name, handler })`
2. Dashboard: add action type `custom_tool` with a `tool_name` config field matching the registered function name
3. When AI triggers the action, widget receives SSE `action` event with `type: "custom_tool"` and `config.tool_name`
4. Widget looks up registered handler and calls it

### Task 4: Backend — add `custom_tool` action type

**Files:**
- Modify: `backend/app/schemas/actions.py`

- [ ] **Step 1: Add `custom_tool` to the `ActionType` literal**

```python
class ActionCreate(BaseModel):
    action_type: Literal[
        "collect_lead", "webhook", "custom_button",
        "slack_message", "web_search", "calendly", "calcom", "custom_tool"
    ]
```

Do the same in any other `Literal[...]` in that file.

- [ ] **Step 2: Update `action_executor.py` CLIENT_SIDE_TYPES**

```python
CLIENT_SIDE_TYPES = {"collect_lead", "custom_button", "calendly", "calcom", "custom_tool"}
```

- [ ] **Step 3: Restart backend**

```bash
docker compose restart backend
```

---

### Task 5: Widget — expose `registerTool` public API

**Files:**
- Modify: `widget/src/index.ts`
- Modify: `widget/src/widget.ts`

- [ ] **Step 1: Check what `index.ts` currently exposes**

Read `widget/src/index.ts`. It likely creates the Widget instance and attaches it to `window`. The public API should be: `window.PulseWidget("registerTool", name, handler)` or as an object method.

- [ ] **Step 2: Add tool registry to Widget class**

In `widget/src/widget.ts`, add to the class:

```typescript
private registeredTools: Map<string, (args?: Record<string, unknown>) => unknown> = new Map();

registerTool(name: string, handler: (args?: Record<string, unknown>) => unknown): void {
  this.registeredTools.set(name, handler);
}
```

Update `onAction` in `sendMessage`:

```typescript
} else if (actionData.type === "custom_tool") {
  const toolName = cfg.tool_name || "";
  const handler = this.registeredTools.get(toolName);
  if (handler) {
    try {
      handler(cfg);
    } catch (e) {
      console.warn(`[PulseLite] Tool "${toolName}" threw an error:`, e);
    }
  } else {
    console.warn(`[PulseLite] No tool registered for "${toolName}"`);
  }
}
```

- [ ] **Step 3: Expose via public API in `index.ts`**

Read `index.ts` first to understand the current interface. Then add:

```typescript
// After widget instantiation, expose a public method
const widgetInstance = new Widget(config);

// Allow page owners to register client-side tools
(window as any).__pulseRegisterTool = (name: string, handler: Function) => {
  widgetInstance.registerTool(name, handler as (args?: Record<string, unknown>) => unknown);
};
```

Add a usage note in the config object or comment:
```
// Usage: window.__pulseRegisterTool("openCart", (args) => { ... })
```

- [ ] **Step 4: Update frontend action form**

In `frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx`, add `custom_tool` to `ACTION_TYPE_LABELS`:

```typescript
const ACTION_TYPE_LABELS: Record<ActionType, string> = {
  // ... existing ...
  custom_tool: "Custom JS Tool",
};
```

Add config fields for `custom_tool` in `ConfigFields`:

```typescript
if (type === "custom_tool") return (
  <div className="space-y-3">
    {textField("tool_name", "Function name", "openCart", true)}
    <p className="text-[11px] text-gray-400">
      Must match the name passed to <code className="bg-gray-100 px-1 rounded">window.__pulseRegisterTool("name", fn)</code> on your page.
    </p>
  </div>
);
```

Also update the `ActionType` in `frontend/src/lib/types.ts`:

```typescript
export type ActionType =
  | "collect_lead" | "webhook" | "custom_button"
  | "slack_message" | "calendly" | "calcom" | "custom_tool";
```

- [ ] **Step 5: Build widget + commit**

```bash
cd /Users/yvanveldeman/dev/pulselite/widget && npm run build
git add widget/src/ widget/dist/widget.js \
        backend/app/schemas/actions.py \
        backend/app/services/action_executor.py \
        frontend/src/lib/types.ts \
        frontend/src/app/\(dashboard\)/chatbots/\[id\]/actions/page.tsx
git commit -m "feat: custom_tool action type + registerTool widget API"
```

---

## Chunk 4: Conversational Parameter Collection (Function Calling)

**What this delivers:** The biggest differentiator. Actions can declare required parameters. Before the bot streams a response, the LLM is given the action list as OpenAI function definitions. If the LLM decides to call a function, we execute it and feed the result back — giving the LLM context to write a better response. For client-side types, we emit an SSE `action` event. The LLM handles parameter collection naturally: if the user hasn't provided `email`, it asks for it.

**Architecture:** One non-streaming LLM call before the RAG streaming response. If it returns a tool call → execute → stream response with tool result in context. If no tool call → stream normally. Adds ~300ms latency per message when actions are configured.

### Task 6: Migration — add `parameters` column

**Files:**
- Create: `backend/alembic/versions/2026_03_11_action_parameters.py`
- Modify: `backend/app/models/actions.py`
- Modify: `backend/app/schemas/actions.py`

- [ ] **Step 1: Create migration**

```python
# backend/alembic/versions/2026_03_11_action_parameters.py
"""add action parameters

Revision ID: add_action_parameters
Revises: add_actions
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "add_action_parameters"
down_revision = "add_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chatbot_actions",
        sa.Column("parameters", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("chatbot_actions", "parameters")
```

- [ ] **Step 2: Run migration**

```bash
make migrate
```

Expected: `Running upgrade add_actions -> add_action_parameters`

- [ ] **Step 3: Add `parameters` to SQLAlchemy model**

In `backend/app/models/actions.py`, add after `is_enabled`:

```python
from sqlalchemy import JSON

parameters: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
```

- [ ] **Step 4: Add `parameters` to Pydantic schemas**

In `backend/app/schemas/actions.py`:

```python
class ActionCreate(BaseModel):
    # ... existing fields ...
    parameters: list[dict] = []
    # Example parameter: {"name": "email", "type": "string", "required": True, "description": "User's email"}


class ActionResponse(BaseModel):
    # ... existing fields ...
    parameters: list[dict]


class ActionUpdate(BaseModel):
    # ... existing fields ...
    parameters: list[dict] | None = None
```

- [ ] **Step 5: Add `parameters` to frontend types**

In `frontend/src/lib/types.ts`:

```typescript
export interface ActionParameter {
  name: string;
  type: "string" | "number" | "boolean";
  required: boolean;
  description: string;
}

export interface Action {
  // ... existing fields ...
  parameters: ActionParameter[];
}

export interface ActionCreate {
  // ... existing fields ...
  parameters?: ActionParameter[];
}
```

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/2026_03_11_action_parameters.py \
        backend/app/models/actions.py \
        backend/app/schemas/actions.py \
        frontend/src/lib/types.ts
git commit -m "feat: add parameters field to chatbot_actions for function calling"
```

---

### Task 7: LLM tool calling support

**Files:**
- Modify: `backend/app/services/llm/base.py`
- Modify: `backend/app/services/llm/openrouter_client.py`
- Create: `backend/tests/unit/test_action_tools.py`

The LLM base client needs a new method `generate_with_tools` that accepts an OpenAI-format tools list and returns either a string response or a tool call object.

- [ ] **Step 1: Add `generate_with_tools` to base class**

```python
# backend/app/services/llm/base.py
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any


class BaseLLMClient(ABC):
    @abstractmethod
    async def stream_generate(self, messages: list[dict], model: str, temperature: float = 0.3, max_tokens: int = 1000) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def generate(self, messages: list[dict], model: str, temperature: float = 0.3, max_tokens: int = 1000) -> str: ...

    async def generate_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """
        Non-streaming call with tool definitions.
        Returns either:
          {"type": "message", "content": "..."}
          {"type": "tool_call", "tool_name": "...", "tool_call_id": "...", "arguments": {...}}
        Default implementation: no tool support, returns message.
        """
        content = await self.generate(messages, model, temperature, max_tokens)
        return {"type": "message", "content": content}
```

- [ ] **Step 2: Implement `generate_with_tools` in OpenRouter client**

In `backend/app/services/llm/openrouter_client.py`, add:

```python
async def generate_with_tools(
    self,
    messages: list[dict],
    model: str,
    tools: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1000,
) -> dict:
    import json
    response = await self._get_client().chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        tools=tools,  # type: ignore[arg-type]
        tool_choice="auto",
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    choice = response.choices[0]
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        call = choice.message.tool_calls[0]
        try:
            args = json.loads(call.function.arguments)
        except Exception:
            args = {}
        return {
            "type": "tool_call",
            "tool_name": call.function.name,
            "tool_call_id": call.id,
            "arguments": args,
        }
    return {"type": "message", "content": choice.message.content or ""}
```

- [ ] **Step 3: Write unit tests for tool definition builder (next task)**

Defer to Task 8. Commit current changes:

```bash
git add backend/app/services/llm/base.py backend/app/services/llm/openrouter_client.py
git commit -m "feat: add generate_with_tools to LLM clients (OpenAI function calling)"
```

---

### Task 8: Action tool definition builder

**Files:**
- Create: `backend/app/services/action_tools.py`
- Create: `backend/tests/unit/test_action_tools.py`

This service converts `ChatbotAction` objects into OpenAI-format tool definitions.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_action_tools.py
import uuid
import pytest
from app.services.action_tools import build_tool_definitions, action_id_for_tool_name
from app.models.actions import ChatbotAction


def _make_action(action_type: str, name: str, trigger: str, parameters: list[dict]) -> ChatbotAction:
    a = ChatbotAction()
    a.id = uuid.uuid4()
    a.chatbot_id = uuid.uuid4()
    a.workspace_id = uuid.uuid4()
    a.action_type = action_type
    a.name = name
    a.trigger_description = trigger
    a.config = {}
    a.is_enabled = True
    a.parameters = parameters
    return a


def test_build_tool_definitions_basic():
    action = _make_action(
        "webhook", "Notify CRM",
        "When user wants to be contacted",
        [{"name": "email", "type": "string", "required": True, "description": "User email"}],
    )
    tools = build_tool_definitions([action])
    assert len(tools) == 1
    t = tools[0]
    assert t["type"] == "function"
    assert "email" in t["function"]["parameters"]["properties"]
    assert "email" in t["function"]["parameters"]["required"]


def test_build_tool_definitions_no_parameters():
    """Actions without parameters still produce a tool definition with no required params."""
    action = _make_action("custom_button", "Book demo", "When user wants a demo", [])
    tools = build_tool_definitions([action])
    assert len(tools) == 1
    assert tools[0]["function"]["parameters"]["required"] == []


def test_tool_name_is_stable_and_unique():
    action = _make_action("webhook", "My Webhook", "trigger", [])
    name = build_tool_definitions([action])[0]["function"]["name"]
    # Name is derived from action id — stable across calls
    assert action_id_for_tool_name(name) == str(action.id)
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
docker compose exec backend pytest tests/unit/test_action_tools.py -v
```

- [ ] **Step 3: Implement `action_tools.py`**

```python
# backend/app/services/action_tools.py
"""
Convert ChatbotAction objects into OpenAI-compatible tool definitions.

Tool names encode the action UUID so we can look up the action after the LLM
returns a tool call. Format: "pulse_<uuid_hex>" (no hyphens — OpenAI names
must match [a-zA-Z0-9_-]{1,64}).
"""
import uuid
from app.models.actions import ChatbotAction

_JSON_TYPE_MAP = {"string": "string", "number": "number", "boolean": "boolean"}


def _tool_name(action_id: uuid.UUID) -> str:
    return f"pulse_{action_id.hex}"


def action_id_for_tool_name(name: str) -> str | None:
    """Reverse: extract action UUID hex from tool name."""
    if name.startswith("pulse_") and len(name) == 38:  # "pulse_" + 32 hex chars
        return str(uuid.UUID(name[6:]))
    return None


def build_tool_definitions(actions: list[ChatbotAction]) -> list[dict]:
    """Return OpenAI-format tool definitions for a list of enabled actions."""
    tools = []
    for action in actions:
        properties: dict = {}
        required: list[str] = []

        for param in (action.parameters or []):
            pname = param.get("name", "")
            if not pname:
                continue
            properties[pname] = {
                "type": _JSON_TYPE_MAP.get(param.get("type", "string"), "string"),
                "description": param.get("description", ""),
            }
            if param.get("required", False):
                required.append(pname)

        tools.append({
            "type": "function",
            "function": {
                "name": _tool_name(action.id),
                "description": action.trigger_description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return tools
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker compose exec backend pytest tests/unit/test_action_tools.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/action_tools.py backend/tests/unit/test_action_tools.py
git commit -m "feat: action_tools service — build OpenAI tool definitions from actions"
```

---

### Task 9: Wire function calling into RAG engine

**Files:**
- Modify: `backend/app/services/rag/engine.py`
- Modify: `backend/app/services/resolution_service.py`

This is the core change. `process_query` gets a new optional `actions` parameter. When actions have parameters, a tool-detection call runs before streaming.

- [ ] **Step 1: Update `process_query` signature**

In `backend/app/services/rag/engine.py`, modify the function signature and add tool-detection logic:

```python
async def process_query(
    db: AsyncSession,
    query: str,
    chatbot: Chatbot,
    conversation_id: uuid.UUID | None = None,
    openrouter_key: str | None = None,
    actions: list | None = None,  # list[ChatbotAction] — passed from resolution_service
) -> AsyncGenerator[str | RAGResult, None]:
    # ... existing retrieval + confidence code unchanged until messages are built ...

    # (Keep everything up to and including building `messages` list)
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_id:
        history = await get_conversation_history(db, conversation_id)
        messages.extend(history)
    messages.append({"role": "user", "content": f"{context_prompt}\n\nUser question: {query}"})

    # --- Tool calling step ---
    tool_result_content: str | None = None
    triggered_action_payload: dict | None = None

    if actions:
        from app.services.action_tools import build_tool_definitions, action_id_for_tool_name
        from app.services.action_service import get_action
        from app.services.action_executor import execute_action, _get_workspace_slack_webhook

        tools = build_tool_definitions(actions)
        if tools:
            provider = "openrouter" if openrouter_key else chatbot.llm_provider
            client = get_llm_client(provider, api_key=openrouter_key)
            tool_result = await client.generate_with_tools(
                messages=messages,
                model=chatbot.llm_model,
                tools=tools,
                temperature=0.0,  # deterministic for action detection
                max_tokens=200,
            )

            if tool_result["type"] == "tool_call":
                action_id_str = action_id_for_tool_name(tool_result["tool_name"])
                if action_id_str:
                    import uuid as _uuid
                    action = await get_action(db, _uuid.UUID(action_id_str), chatbot.workspace_id)
                    if action:
                        slack_webhook = await _get_workspace_slack_webhook(db, chatbot.workspace_id)
                        context = {
                            "conversation_id": str(conversation_id) if conversation_id else "",
                            "message": query,
                            "response": "",
                            **tool_result["arguments"],
                        }
                        status, client_payload = await execute_action(action, context, slack_webhook)
                        if client_payload:
                            triggered_action_payload = client_payload
                            tool_result_content = f"Action '{action.name}' triggered successfully."
                        else:
                            tool_result_content = f"Action '{action.name}' executed with status: {status}."

                        # Log action event
                        from app.models.actions import ActionEvent
                        event = ActionEvent(
                            id=_uuid.uuid4(),
                            workspace_id=chatbot.workspace_id,
                            chatbot_id=chatbot.id,
                            conversation_id=conversation_id,
                            action_id=action.id,
                            action_type=action.action_type,
                            payload=context,
                            status=status,
                        )
                        db.add(event)
                        await db.flush()

    # If a tool was called, inject result into messages before streaming
    if tool_result_content:
        messages.append({"role": "assistant", "content": tool_result_content})

    # Yield triggered action payload before streaming (for SSE emission)
    if triggered_action_payload:
        yield triggered_action_payload  # resolution_service handles this specially

    async for token in stream_response(messages, chatbot, openrouter_key=openrouter_key):
        yield token
```

- [ ] **Step 2: Update `resolution_service.py` to load actions and pass them to `process_query`**

In `backend/app/services/resolution_service.py`, update the `handle_message` function to load enabled actions before calling `process_query`, and handle the action payload yielded before tokens:

```python
    # Load enabled actions for function calling
    from app.services.action_service import list_enabled_actions
    enabled_actions = await list_enabled_actions(db, workspace_id, chatbot.id)
    actions_with_params = [a for a in enabled_actions if a.parameters]

    rag_result: RAGResult | None = None
    full_response = ""
    inline_action_payloads: list[dict] = []

    async for item in process_query(
        db, message, chatbot, conversation_id,
        openrouter_key=openrouter_key,
        actions=actions_with_params if actions_with_params else None,
    ):
        if isinstance(item, RAGResult):
            rag_result = item
            continue
        if isinstance(item, dict):
            # Triggered action payload (client-side) from function calling
            inline_action_payloads.append(item)
            continue
        full_response += item
        yield ResolutionEvent(type="token", data=item, conversation_id=conversation_id)
```

Then after `await db.flush()`, yield inline action payloads and remove the old `run_actions` call for actions that were already handled via function calling:

```python
    # Yield function-call-triggered action events
    for payload in inline_action_payloads:
        yield ResolutionEvent(type="action", data=payload, conversation_id=conversation_id)

    # Post-response: fire actions WITHOUT parameters (old trigger-and-forget path)
    # Actions WITH parameters were handled by function calling above
    try:
        from app.services.action_executor import run_actions
        actions_without_params = [a for a in enabled_actions if not a.parameters]
        if actions_without_params:
            client_payloads = await run_actions(
                db_session=db,
                workspace_id=workspace_id,
                chatbot_id=chatbot.id,
                conversation_id=conversation_id,
                user_message=message,
                bot_response=full_response,
            )
            for payload in client_payloads:
                yield ResolutionEvent(type="action", data=payload, conversation_id=conversation_id)
    except Exception:
        logger.exception("Action execution failed — continuing without actions")
```

- [ ] **Step 3: Restart backend + test**

```bash
docker compose restart backend
```

Create an action with parameters (e.g., `webhook` type with parameter `email: string`). Send a message that should trigger it. Confirm:
1. The LLM asks for email if not provided
2. On providing email, the webhook fires with the email in the payload

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/rag/engine.py backend/app/services/resolution_service.py
git commit -m "feat: LLM function calling — actions with parameters trigger pre-response"
```

---

### Task 10: Parameter editor UI in Actions page

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx`

Add a collapsible "Parameters" section to the action add form. Each parameter has: name, type (string/number/boolean), required toggle, description.

- [ ] **Step 1: Add parameter state to the form**

```typescript
// In EMPTY_FORM, add:
parameters: [] as ActionParameter[],
```

- [ ] **Step 2: Add parameter editor component**

```tsx
function ParameterEditor({
  parameters,
  onChange,
}: {
  parameters: ActionParameter[];
  onChange: (params: ActionParameter[]) => void;
}) {
  function addParam() {
    onChange([...parameters, { name: "", type: "string", required: false, description: "" }]);
  }
  function removeParam(i: number) {
    onChange(parameters.filter((_, idx) => idx !== i));
  }
  function updateParam(i: number, field: keyof ActionParameter, value: unknown) {
    onChange(parameters.map((p, idx) => idx === i ? { ...p, [field]: value } : p));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
          Parameters (optional)
        </label>
        <button
          type="button"
          onClick={addParam}
          className="text-[11px] text-primary-500 font-medium hover:text-primary-600"
        >
          + Add parameter
        </button>
      </div>
      <p className="text-[11px] text-gray-400">
        If you add parameters, the AI will collect them from the user before triggering this action.
      </p>
      {parameters.map((param, i) => (
        <div key={i} className="flex gap-2 items-start p-3 bg-white border border-[#e8e2d9] rounded-lg">
          <input
            value={param.name}
            onChange={(e) => updateParam(i, "name", e.target.value)}
            placeholder="name"
            className="w-24 px-2 py-1.5 text-xs border border-[#e8e2d9] rounded-md focus:outline-none focus:border-primary-400"
          />
          <select
            value={param.type}
            onChange={(e) => updateParam(i, "type", e.target.value)}
            className="w-24 px-2 py-1.5 text-xs border border-[#e8e2d9] rounded-md focus:outline-none focus:border-primary-400 bg-white"
          >
            <option value="string">string</option>
            <option value="number">number</option>
            <option value="boolean">boolean</option>
          </select>
          <input
            value={param.description}
            onChange={(e) => updateParam(i, "description", e.target.value)}
            placeholder="description"
            className="flex-1 px-2 py-1.5 text-xs border border-[#e8e2d9] rounded-md focus:outline-none focus:border-primary-400"
          />
          <label className="flex items-center gap-1 text-[11px] text-gray-500 whitespace-nowrap mt-1.5">
            <input
              type="checkbox"
              checked={param.required}
              onChange={(e) => updateParam(i, "required", e.target.checked)}
              className="accent-primary-500"
            />
            required
          </label>
          <button
            type="button"
            onClick={() => removeParam(i)}
            className="text-gray-300 hover:text-red-400 mt-0.5"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Add `ParameterEditor` to the form, after `ConfigFields`**

```tsx
<ParameterEditor
  parameters={form.parameters ?? []}
  onChange={(params) => setForm({ ...form, parameters: params })}
/>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(dashboard\)/chatbots/\[id\]/actions/page.tsx \
        frontend/src/lib/types.ts
git commit -m "feat: parameter editor UI in actions form"
```

---

## Chunk 5: Stripe + Salesforce Action Types

**What this delivers:** Two additional action types that use the workspace's existing integrations (configured in Settings → Integrations). `stripe_lookup` queries a customer's subscription status. `salesforce_ticket` creates a case in Salesforce.

### Task 11: Stripe action

**Files:**
- Modify: `backend/app/schemas/actions.py`
- Modify: `backend/app/services/action_executor.py`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx`
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Add `stripe_lookup` to action type literals (backend + frontend)**

Backend (`schemas/actions.py`):
```python
action_type: Literal[
    "collect_lead", "webhook", "custom_button", "slack_message",
    "calendly", "calcom", "custom_tool", "stripe_lookup", "salesforce_ticket"
]
```

Frontend (`types.ts`):
```typescript
export type ActionType =
  | "collect_lead" | "webhook" | "custom_button" | "slack_message"
  | "calendly" | "calcom" | "custom_tool" | "stripe_lookup" | "salesforce_ticket";
```

- [ ] **Step 2: Add Stripe executor in `action_executor.py`**

```python
async def _execute_stripe_lookup(action: ChatbotAction, context: dict, db_session) -> str:
    """
    Look up a Stripe customer by email and return subscription status.
    Requires workspace Stripe integration to be configured.
    """
    from sqlalchemy import select
    from app.models.integrations import IntegrationConfig

    workspace_id_val = action.workspace_id
    result = await db_session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id_val,
            IntegrationConfig.integration_type == "stripe",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    integration = result.scalar_one_or_none()
    if not integration or not integration.config.get("api_key"):
        return "error:stripe_not_configured"

    email = context.get("email", "")
    if not email:
        return "error:no_email"

    try:
        import stripe
        stripe.api_key = integration.config["api_key"]
        customers = stripe.Customer.list(email=email, limit=1)
        if not customers.data:
            return "ok:no_customer"
        customer = customers.data[0]
        subs = stripe.Subscription.list(customer=customer.id, status="active", limit=1)
        plan = subs.data[0].items.data[0].price.nickname if subs.data else "none"
        return f"ok:plan={plan}"
    except Exception as exc:
        logger.warning(f"Stripe lookup failed: {exc}")
        return "error:stripe_api_failed"
```

Add `stripe_lookup` to `execute_action`:

```python
if action.action_type == "stripe_lookup":
    # db_session not available here — pass None, handled in resolution_service
    status = await _execute_stripe_lookup(action, context, None)
    return status, None
```

Note: `_execute_stripe_lookup` needs the db session. Pass it via `execute_action` by adding an optional `db` parameter to the function signature.

- [ ] **Step 3: Add config fields in UI**

```typescript
if (type === "stripe_lookup") return (
  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
    <p className="text-[12px] text-amber-700 font-medium">Requires Stripe integration</p>
    <p className="text-[11px] text-amber-600 mt-0.5">
      Configure your Stripe API key in Settings → Integrations first.
      Add an <code>email</code> parameter so the AI can collect it before lookup.
    </p>
  </div>
);
```

---

### Task 12: Salesforce action

**Files:**
- Modify: `backend/app/services/action_executor.py`

- [ ] **Step 1: Add `_execute_salesforce_ticket` to executor**

```python
async def _execute_salesforce_ticket(action: ChatbotAction, context: dict, db_session) -> str:
    """Create a Salesforce Case from the current conversation context."""
    from sqlalchemy import select
    from app.models.integrations import IntegrationConfig

    result = await db_session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == action.workspace_id,
            IntegrationConfig.integration_type == "salesforce",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        return "error:salesforce_not_configured"

    cfg = integration.config
    try:
        from simple_salesforce import Salesforce
        sf = Salesforce(
            username=cfg.get("username"),
            password=cfg.get("password"),
            security_token=cfg.get("security_token"),
        )
        sf.Case.create({
            "Subject": f"Chat inquiry: {context.get('message', '')[:80]}",
            "Description": context.get("message", ""),
            "Origin": "Web",
            "SuppliedEmail": context.get("email", ""),
        })
        return "ok"
    except Exception as exc:
        logger.warning(f"Salesforce ticket creation failed: {exc}")
        return "error:salesforce_api_failed"
```

Add `salesforce_ticket` to `execute_action`:
```python
if action.action_type == "salesforce_ticket":
    status = await _execute_salesforce_ticket(action, context, None)
    return status, None
```

Same note: pass `db` parameter through `execute_action`.

- [ ] **Step 2: Add config fields in UI**

```typescript
if (type === "salesforce_ticket") return (
  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
    <p className="text-[12px] text-blue-700 font-medium">Requires Salesforce integration</p>
    <p className="text-[11px] text-blue-600 mt-0.5">
      Configure Salesforce in Settings → Integrations. Add an <code>email</code> parameter
      to attach the contact's email to the created case.
    </p>
  </div>
);
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/action_executor.py \
        backend/app/schemas/actions.py \
        frontend/src/lib/types.ts \
        frontend/src/app/\(dashboard\)/chatbots/\[id\]/actions/page.tsx
git commit -m "feat: Stripe lookup + Salesforce ticket action types"
```

---

## Summary

After all chunks, PulseLite actions match or exceed Chatbase:

| Feature | Chatbase | PulseLite after plan |
|---|---|---|
| Lead form → webhook notification | ✅ | ✅ Chunk 1 |
| HMAC-signed webhook payloads | ✅ | ✅ Chunk 1 |
| Inline Calendly/Cal.com embed | ✅ | ✅ Chunk 2 (iframe card) |
| Client-side JS tools (registerTools) | ✅ | ✅ Chunk 3 |
| Conversational parameter collection | ✅ (function calling) | ✅ Chunk 4 |
| Stripe integration | ✅ | ✅ Chunk 5 |
| Salesforce ticket | ✅ | ✅ Chunk 5 |
| Custom webhook actions | ✅ | ✅ (already built) |
| Slack notification | ✅ | ✅ (already built) |
| Web search | ✅ (premium) | ⏳ Future — requires pre-RAG pipeline changes |
| Collect lead (form capture) | ✅ | ✅ (already built) |
| Custom button | ✅ | ✅ (already built) |

**Not in scope (future):** Web search (requires real-time search API + RAG pipeline rewrite), Zapier/Make native integration (can be done via webhook), multi-step agent loops (Chunk 4 covers one tool call per turn; chained calls need further work).
