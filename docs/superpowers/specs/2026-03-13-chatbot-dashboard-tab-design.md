# Chatbot Dashboard Tab Design

**Date:** 2026-03-13

## Goal

Add a "Dashboard" tab as the first tab in the chatbot detail view, giving users a single-page overview of their chatbot's performance, operational health, and configuration.

## Problem

Currently, chatbot insights are scattered across the workspace-level dashboard (which aggregates all chatbots) and individual configuration tabs. There's no chatbot-scoped overview that lets a user quickly assess how a specific bot is performing, what topics it's handling, where it's failing, and what its current configuration looks like.

## Design

### Layout

Sectioned scroll layout within the existing chatbot detail tab structure. A range selector (7d / 30d / 90d) at the top-right controls the time window for all data-driven sections.

### Tab placement and routing

"Dashboard" becomes the first tab in the chatbot detail layout. It uses `segment: null` (the index route), making it the default view when navigating to `/chatbots/:id`.

The current Knowledge tab (which currently has `segment: null`) moves to `segment: "sources"`. This works because a `sources/page.tsx` sub-route already exists. The `App.tsx` route config changes:
- Index route (`<Route index>`) → `ChatbotDashboardPage` (new)
- Knowledge/Sources route → explicit `<Route path="sources">` pointing to the existing `KnowledgePage`

### Sections (top to bottom)

#### 1. KPI Row (4 cards, single row)

| Metric | Source | Delta |
|---|---|---|
| Conversations | `getDashboardData` with `chatbot_id` | vs previous period |
| Resolution Rate | `getDashboardData` with `chatbot_id` | percentage point change |
| Avg Sentiment | `getSentimentTrends` with `chatbot_id` | absolute change |
| Positive Feedback | `getDashboardData` with `chatbot_id` | thumbs up count + ratio |

Each card shows: label, large number, trend indicator (green up / red down / gray neutral).

#### 2. Confidence & Resolution (full-width card)

Left side: stacked horizontal bar showing confident % / low-confidence % / escalated %.
Right side: three counters — Resolved, Escalated, Unresolved (with color-coded numbers).

Source: `getDashboardData` with `chatbot_id`.

#### 3. Topics + Knowledge Gaps (2-column)

**Left — Top Topics:** List of top 4-5 topics with resolution percentage badges (green/yellow/red based on threshold).

**Right — Knowledge Gaps:** List of top 4-5 unanswered questions with occurrence count. "View all →" link navigates to the Knowledge tab or a filtered view.

Source: `getDashboardData` (topics) and `getGapClusters` (gaps), both with `chatbot_id`.

#### 4. Recent Conversations (full-width card)

Last 5 conversations with: first message preview, status badge (Resolved / Escalated / Unresolved), relative timestamp. "View all →" link navigates to the Logs page filtered by this chatbot.

Source: Existing `getConversations` with `chatbot_id` filter and `limit=5` (backend already supports both params; frontend function needs `limit` added).

#### 5. Crawl Health + Feedback (2-column)

**Left — Crawl & Indexing:** Pages indexed count, knowledge base count, last crawl timestamp, content freshness indicator, failed pages count.

Source: Chatbot's knowledge bases and their documents (already available via chatbot detail or a new summary endpoint).

**Right — Feedback:** Thumbs up/down counts with large icons, plus last 2-3 negative feedback messages for quick visibility.

Source: `getDashboardData` with `chatbot_id` (feedback counts) + new field or endpoint for recent negative feedback text.

#### 6. Configuration (full-width card)

**Top row (read-only, 3-column grid):**
- Model: name, temperature, max tokens
- Retrieval: top-k, reranking on/off, confidence threshold
- Persona: tone, language, escalation behavior

**Middle — Linked Actions:** List of connected actions with name, trigger description, and on/off toggle. Toggle calls `updateAction(workspaceId, chatbotId, actionId, { enabled })` via the existing `PUT /api/v1/workspaces/{workspace_id}/chatbots/{chatbot_id}/actions/{action_id}` endpoint.

**Bottom — Knowledge Sources:** List of knowledge bases with name, page count, last updated timestamp.

Source: Chatbot detail (already loaded by layout), actions list endpoint, knowledge bases endpoint.

### Backend Changes

#### 1. Add `days` query parameter to `GET /dashboard`

The current endpoint hardcodes a 7-day window (`now - timedelta(days=7)`). Add an optional `days: int = Query(30, ge=1, le=90)` parameter and use it for all time-windowed queries (conversations, resolution, feedback, topics). This is required for the range selector to work.

#### 2. Add `chatbot_id` filter to `GET /sentiment-trends`

Add an optional `chatbot_id` query parameter. Implementation note: `ConversationAnalysis` does not have a direct `chatbot_id` column — filtering requires joining through `Conversation.chatbot_id`, similar to how `top_topics` is already implemented in the same file.

#### 3. Modify `top_topics` query to return per-topic resolution rate

The current query only counts `autonomous_resolved = TRUE` conversations, so every topic implicitly has 100% resolution. Change the query to count both total and resolved conversations per topic, returning `{ topic, total_count, resolved_count, resolution_rate }`. This enables the green/yellow/red resolution badges in the UI.

#### 4. Recent negative feedback

Add a `recent_negative_feedback` field (last 3 thumbs-down messages with text) to the dashboard response when `chatbot_id` is provided. This avoids a separate endpoint.

### Frontend Changes

#### New file: `frontend/src/app/(dashboard)/chatbots/[id]/page.tsx` (index route = Dashboard)

Single component that:
1. Reads `chatbotId` from route params and `workspaceId` from workspace store
2. Maintains `range` state (7d/30d/90d, default 30d)
3. Fetches dashboard data, sentiment trends, gap clusters, conversations, and chatbot detail in parallel on mount and range change
4. Renders all 6 sections in the sectioned scroll layout

#### Modified: `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx`

Update the `TABS` array:
- Dashboard: `{ label: "Dashboard", segment: null, Icon: IconDashboard }` (first entry, index route)
- Knowledge: change `segment: null` → `segment: "sources"`
- All other tabs unchanged

#### Modified: `frontend/src/App.tsx`

- Index route (`<Route index>`) → new `ChatbotDashboardPage`
- Add explicit `<Route path="sources" element={<KnowledgePage />} />`

#### Modified: `frontend/src/lib/api-functions.ts`

- `getSentimentTrends`: add optional `chatbotId` parameter, pass as `?chatbot_id=` query param
- `getGapClusters`: add optional `chatbotId` parameter (backend already supports it, frontend doesn't expose it)
- `getConversations`: add optional `limit` parameter (backend already supports it, frontend doesn't expose it)

### Data reuse

Most data comes from existing endpoints:
- `getDashboardData(workspaceId, range, chatbotId)` — KPIs, confidence, topics, feedback counts (**already supports `chatbot_id`** on both backend and frontend; **needs `days` param added to backend**)
- `getGapClusters(workspaceId, { chatbot_id })` — knowledge gaps (**backend supports `chatbot_id`**, frontend function needs to expose it)
- `getSentimentTrends(workspaceId, range, chatbotId)` — sentiment (**needs `chatbot_id` added to both backend endpoint and frontend function**)
- `getConversations(workspaceId, { chatbot_id, limit })` — recent conversations (**backend supports both**, frontend needs `limit` param)

The configuration section reads from the chatbot object already loaded by the layout, plus existing actions and knowledge base endpoints.

### Interactive elements

- **Range selector:** 7d / 30d / 90d pill buttons, re-fetches all time-dependent data on change
- **Action toggles:** on/off switches that call `updateAction()` to toggle the action's enabled state
- **"View all →" links:** Navigate to relevant pages (Knowledge tab, Logs page with chatbot filter)
- **Conversation rows:** Clickable, navigate to conversation detail

### Empty states

- New chatbot with no conversations: show KPI cards with zeros and a friendly "No conversations yet" message in the conversations section
- No knowledge gaps: hide the gaps card or show "No gaps detected"
- No actions configured: show "No actions linked" with a link to the Actions tab
- No knowledge base: show "No knowledge base yet" with a link to add a URL in the Knowledge tab

## Non-goals

- Real-time WebSocket updates (polling on mount is sufficient)
- Exportable reports or PDF generation
- Custom date range picker (fixed 7d/30d/90d is enough)
- Editable configuration fields (read-only summary; editing happens in dedicated tabs)
