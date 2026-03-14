# Setup Page — Vertical Timeline Wizard

## Goal

Replace the current single-step-at-a-time setup page (`/chatbots/:id/setup`) with a vertical timeline that shows all 4 steps simultaneously. Completed steps collapse to summary chips, the active step expands inline, and pending steps appear grayed out.

## Scope

Single-file rewrite of `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx`. No new components. All existing API calls, Socket.IO event handlers, and state management stay the same — only the JSX layout changes.

## Four Steps

| # | id | Label | Can be active on setup page? |
|---|-----|-------|------------------------------|
| 1 | `website` | Your website | No — always rendered as completed chip |
| 2 | `crawl` | Crawl & analyse | Yes — covers `crawling` + `configuring` phases |
| 3 | `review` | Review config | Yes — review form with autoconfig results |
| 4 | `golive` | Go live | Yes — terminal step, embed snippet |

## Timeline Layout

- Container: `max-w-2xl mx-auto py-10 px-4`
- Each step row: `flex gap-3.5`
  - Spine column: fixed 26px wide, `flex flex-col items-center` — circle + vertical connecting line
  - Content column: `flex-1` — chip (completed) or expanded card (active) or muted label (pending)
- Connecting line: 2px wide, stretches between circles
  - `bg-primary-500` between two completed steps
  - `bg-gray-200` otherwise

## Step Circle States

| State | Appearance |
|-------|-----------|
| **Done** | `w-6.5 h-6.5` filled `bg-primary-500` circle, white checkmark icon inside |
| **Active** | `w-6.5 h-6.5` filled `bg-primary-500` circle, white step number inside |
| **Pending** | `w-6.5 h-6.5` circle with `border-2 border-gray-300`, gray step number |
| **Error** | `w-6.5 h-6.5` filled `bg-amber-500` circle, white exclamation icon |

## Step States & Content

### Step 1 — Your website (always completed)

**Chip:** `bg-green-50 border border-green-200 rounded-lg px-3 py-2`
- Text: just `{chatbot.name}` — the name is typically set to the domain during creation (e.g., "acmecorp"). No separate hostname parsing needed.
- Read-only, not clickable

### Step 2 — Crawl & analyse

**Active content (covers both `crawling` and `configuring` phases):**

During `crawling`:
- Three progress sub-steps (existing UI):
  1. Discovering pages — spinner or green check, count
  2. Fetching pages — progress bar with `pagesQueued / pagesDiscovered`
  3. Indexing content — progress bar (shown when crawl completed and docs indexing)

During `configuring`:
- "AI is configuring your bot…" with spinner
- 5-minute timeout warning (existing behavior)

**Error states** (step stays expanded, circle turns amber):
- Crawl failed: existing red alert with "Start over" / "Go to settings" buttons
- Configuring timeout: existing amber alert

**`setup_failed` state** (autoconfig failed, not crawl failed):
- Reuses the existing "Autoconfig failed" UI: amber alert icon, "Your bot was created but couldn't be auto-configured", "Go to settings →" button
- Circle turns amber

**Collapsed chip** (after `setup_status` transitions to `ready`):
- Text: `{pages_queued} pages crawled · AI config ready`

### Step 3 — Review config

**Active content:**
- Existing review form: bot name, welcome message, system prompt, fallback message, tone selector, language dropdown, brand color picker
- "Skip" button → navigates to `/chatbots/${id}` (user can find embed code on the detail page)
- "Save & finish" button → saves and advances to step 4

**Collapsed chip** (after save succeeds):
- Text: `{reviewName} · {tone} · {language}`

### Step 4 — Go live (terminal)

**Active content:**
- Embed `<script>` tag displayed in a code block: `<script src="https://{host}/widget/{chatbot.id}.js"></script>`
- "Copy" button next to the code block
- "Go to dashboard →" button that navigates to `/chatbots/${id}`

Step 4 never collapses — it is always the terminal active state.

## State Machine

Existing `getSetupStep()` function is adapted. A local `step4Active` boolean is added:

| `setup_status` | `step4Active` | Active step |
|----------------|---------------|-------------|
| `crawling` | `false` | 2 |
| `configuring` | `false` | 2 |
| `ready` | `false` | 3 |
| `setup_failed` | `false` | 2 (error state) |
| After save succeeds | `true` | 4 |
| `done` (on initial load) | — | Redirect to `/chatbots/${id}` |

### Step completion derivation

- Step 1: always completed (chatbot exists, we're on the setup page)
- Step 2: completed when `setup_status` is `ready` or `done`, or `step4Active` is true
- Step 3: completed when `step4Active` is true

## Save Flow Change

Current: "Save & finish" calls `updateChatbot(…, { setup_status: "done" })` then navigates to `/chatbots/${id}`.

New: "Save & finish" calls `updateChatbot(…, { setup_status: "done" })`, then instead of navigating, sets `step4Active = true`. The "Go to dashboard →" button in step 4 handles navigation.

**Important:** The `chatbot:status_changed` handler currently redirects on `setup_status === "done"`. When `step4Active` is true, suppress this redirect — the status change was triggered by our own save action, not an external event. Guard: `if (step === "done" && !step4Active) navigate(…)`.

**Browser refresh during step 4:** If the user refreshes after save, `setup_status` is `"done"` so the page redirects to the detail page. This is acceptable — the embed snippet is also available on the chatbot detail page.

## Data Sources

No new API calls or Socket.IO events. All data comes from existing state:

- **Step 1 chip:** `chatbot.name`
- **Step 2 progress:** `crawlStatus` state updated by `crawl:progress` and `crawl:completed` Socket.IO events
- **Step 2→3 transition:** `chatbot:status_changed` Socket.IO event
- **Step 3 form:** populated from `chatbot` fields after autoconfig refetch
- **Step 4 snippet:** `chatbot.id` (already available) + window.location.origin for the host

## What Does NOT Change

- All Socket.IO event handlers and reconnect logic
- All API calls (`getChatbot`, `getCrawlStatus`, `updateChatbot`)
- Review form fields and validation
- Error handling (crawl failed, configuring timeout, setup_failed)
- Loading and error states (spinner on initial load, error message)
- The `/chatbots/new` page (step 1 input page) — unchanged
