# PulseLite Copilot — Design Spec

**Date:** 2026-03-11
**Status:** Approved

---

## What We're Building

An in-app AI copilot embedded in the PulseLite dashboard. The copilot knows what's on screen, can fetch any data in the workspace, navigate the app, render standalone UI components in a side panel, and make write operations — anything the user can do. It runs as a persistent right-anchored panel toggled with ⌘J.

---

## Layout

```
┌────────────────────────────────────────────────────────────────┐
│  TopBar                                                        │
├──────┬─────────────────────────────┬─────────────┬────────────┤
│      │                             │             │            │
│ Nav  │   Main content              │  Component  │   Chat     │
│ bar  │   (flex-1, shrinks)         │  Panel      │   Panel    │
│      │                             │  (0→480px)  │   (280px)  │
│      │                             │  CSS anim   │   fixed    │
└──────┴─────────────────────────────┴─────────────┴────────────┘
```

- **Chat panel** (280px): always visible when copilot is open. Pinned to right edge. Contains conversation history, streaming response, input.
- **Component panel** (0–480px): slides in LEFT of chat panel when AI calls `render_panel`. CSS `width` transition — no JS animation needed. Dismissed with ✕ or `close_panel` tool call.
- **Main content**: `flex-1`, shrinks naturally as panels open.
- **Toggle**: ⌘J. Persisted to localStorage so it reopens in the same state.

---

## Architecture

### Five pieces

1. **CopilotProvider** — React context. Holds `isOpen`, `context` (current page state), `activePanel` (component + props or null). Handles ⌘J.

2. **CopilotPanel** — renders the two-column panel UI. Chat column always visible. Component column CSS-transitioned.

3. **ComponentRegistry** — map of `componentName → React component`. Each entry is a standalone panel component.

4. **`/api/v1/copilot/chat`** — SSE endpoint. Receives `{ messages, context, workspace_id }`. Builds system prompt, runs LLM function calling via OpenRouter, executes server-side tools inline, emits client-side tools as SSE action events.

5. **`useCopilot()` hook** — used by pages to register their context on mount/data-load.

### Request/response flow

```
Frontend                          Backend
   │                                 │
   │── POST /api/v1/copilot/chat ──▶ │
   │   { messages, context }         │
   │                                 │── LLM call (function calling)
   │◀── SSE: token ──────────────── │   tool: fetch_conversations(...)
   │◀── SSE: token ──────────────── │── DB query → result back to LLM
   │◀── SSE: action (render_panel) ─ │   tool: render_panel(...)
   │◀── SSE: token ──────────────── │── continues streaming
   │◀── SSE: done ───────────────── │
```

Server-side tools execute inline and feed results back into the LLM context. Client-side tools (`render_panel`, `navigate`, `patch_store`, `close_panel`) are emitted as SSE `action` events and handled by `CopilotPanel`.

---

## Context Schema

Sent with every message. Pages register this via `useCopilot().register(...)`.

```typescript
interface CopilotPageContext {
  page: string                    // e.g. "dashboard", "chatbot-settings"
  chatbot_id?: string
  conversation_id?: string
  data: Record<string, unknown>   // whatever is visible on screen
}
```

Examples:
```json
// Dashboard
{ "page": "dashboard", "data": { "metrics": { "total_conversations": 142, ... } } }

// Chatbot settings
{ "page": "chatbot-settings", "chatbot_id": "abc", "data": { "chatbot": { "name": "Support Bot", "llm_model": "gpt-4o-mini", "confidence_threshold": 0.7 } } }

// Conversations list
{ "page": "conversations", "data": { "active_filters": { "escalated": true }, "count": 12 } }
```

---

## Tool Definitions

### Server-side tools (execute on backend, result → LLM)

| Tool | Args | Action |
|---|---|---|
| `fetch_conversations` | `filters?` (escalated, chatbot_id, date_range, limit) | Returns conversation list |
| `fetch_conversation` | `conversation_id` | Returns conversation + messages |
| `fetch_chatbots` | — | Returns workspace chatbot list |
| `fetch_chatbot` | `chatbot_id` | Returns single chatbot config |
| `fetch_metrics` | `period?` (7d, 30d) | Returns dashboard KPI data |
| `fetch_credits` | — | Returns credit balance + usage |
| `fetch_documents` | `chatbot_id` | Returns knowledge base docs |
| `fetch_actions` | `chatbot_id` | Returns configured actions |
| `update_chatbot` | `chatbot_id`, `fields` | Updates chatbot fields (partial) |
| `create_chatbot` | `name`, `url?` | Creates chatbot, optionally triggers crawl |
| `delete_chatbot` | `chatbot_id` | Deletes chatbot |
| `run_crawl` | `chatbot_id`, `url` | Triggers crawl job |
| `create_action` | `chatbot_id`, `action_type`, `name`, `trigger_description`, `config` | Creates action |
| `delete_action` | `chatbot_id`, `action_id` | Deletes action |

### Client-side tools (SSE action events, handled by CopilotPanel)

| Tool | Args | Frontend action |
|---|---|---|
| `render_panel` | `component`, `props` | Renders component in left panel |
| `close_panel` | — | Dismisses component panel |
| `navigate` | `route` | Calls Next.js router.push |
| `patch_store` | `store`, `data` | Updates Zustand store (optimistic UI) |

---

## Component Registry

Standalone panel components. Each accepts minimal props and fetches its own data.

```typescript
export const ComponentRegistry: Record<string, React.ComponentType<any>> = {
  ConversationList:      ConversationListPanel,    // props: { filters?, chatbot_id? }
  ConversationDetail:    ConversationDetailPanel,  // props: { conversation_id }
  MetricsDashboard:      MetricsDashboardPanel,    // props: { period? }
  ChatbotList:           ChatbotListPanel,         // props: { }
  DocumentList:          DocumentListPanel,        // props: { chatbot_id }
  ActionsList:           ActionsListPanel,         // props: { chatbot_id }
  CreditBalance:         CreditBalancePanel,       // props: { }
  LLMSettingsPanel:      LLMSettingsPanel,         // props: { chatbot_id }
  PersonaSettingsPanel:  PersonaSettingsPanel,     // props: { chatbot_id }
  WidgetSettingsPanel:   WidgetSettingsPanel,      // props: { chatbot_id }
}
```

---

## Frontend File Structure

### New files

```
frontend/src/
├── components/copilot/
│   ├── CopilotProvider.tsx     # Context, useCopilot hook, ⌘J handler
│   ├── CopilotPanel.tsx        # Two-column panel layout
│   ├── CopilotChat.tsx         # Chat column: history, streaming, input
│   ├── ComponentPanel.tsx      # Left column: renders registry component
│   ├── registry.tsx            # ComponentRegistry map
│   └── api.ts                  # SSE client for /api/v1/copilot/chat
├── panels/
│   ├── ConversationListPanel.tsx
│   ├── ConversationDetailPanel.tsx
│   ├── MetricsDashboardPanel.tsx
│   ├── ChatbotListPanel.tsx
│   ├── DocumentListPanel.tsx
│   ├── ActionsListPanel.tsx
│   ├── CreditBalancePanel.tsx
│   ├── LLMSettingsPanel.tsx
│   ├── PersonaSettingsPanel.tsx
│   └── WidgetSettingsPanel.tsx
```

### Existing files modified

| File | Change |
|---|---|
| `app/(dashboard)/layout.tsx` | Wrap with `CopilotProvider`, add `CopilotPanel` inside layout flex |
| `app/(dashboard)/chatbots/[id]/SettingsTab.tsx` | Split into three panels, SettingsTab stacks them |
| Each dashboard page | Add `useCopilot().register(...)` in existing data-load `useEffect` |

---

## Backend File Structure

### New files

```
backend/app/
├── api/v1/copilot.py           # POST /api/v1/copilot/chat SSE endpoint
├── services/copilot/
│   ├── system_prompt.py        # Builds system prompt from context + tool list
│   ├── tools.py                # Tool definitions (OpenAI function calling format)
│   └── executor.py             # Executes server-side tool calls
```

### Existing files modified

| File | Change |
|---|---|
| `app/main.py` | Register copilot router |

---

## Backend: Endpoint + Execution

```python
# POST /api/v1/copilot/chat
# Auth: Depends(get_current_user) — workspace membership validated
# Body: { messages: [...], context: {...}, workspace_id: UUID }
# Response: SSE stream

async def copilot_chat(body, db, current_user):
    system_prompt = build_system_prompt(body.context)
    messages = [{"role": "system", "content": system_prompt}] + body.messages
    tools = get_tool_definitions()

    async def stream():
        while True:
            result = await llm.generate_with_tools(messages, model, tools)
            if result["type"] == "message":
                yield token_event(result["content"])
                yield done_event()
                break
            elif result["type"] == "tool_call":
                tool_name = result["tool_name"]
                args = result["arguments"]
                if tool_name in CLIENT_SIDE_TOOLS:
                    yield action_event(tool_name, args)
                    messages.append(tool_result_message(tool_name, result["tool_call_id"], "ok"))
                else:
                    tool_result = await execute_tool(db, body.workspace_id, tool_name, args)
                    messages.append(tool_result_message(tool_name, result["tool_call_id"], tool_result))
                # loop: LLM continues with tool result in context

    return EventSourceResponse(stream())
```

The loop allows multi-step reasoning: LLM can call `fetch_conversations` to get data, then call `render_panel` to display it, then stream a text response — all in one user turn.

---

## Security

- Endpoint requires `get_current_user` — no unauthenticated access
- All tool calls validate `workspace_id` matches the authenticated user's membership — same `get_workspace` dependency used elsewhere
- Write tools (`update_chatbot`, `delete_chatbot`, etc.) go through the same service layer as the regular API — no privilege bypass
- No API key exposure to frontend — LLM called server-side only

---

## What Is Not In Scope

- Voice input/output
- Copilot suggestions proactively pushed (no polling, user-initiated only)
- Multi-turn memory across sessions (conversation history is in-session only, not persisted)
- Copilot in the public chat widget (this is dashboard-only)
