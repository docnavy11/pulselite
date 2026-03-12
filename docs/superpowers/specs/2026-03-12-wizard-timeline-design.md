# Chatbot Creation Wizard — Vertical Timeline Redesign

## Goal

Replace the horizontal progress bar at the top of the chatbot creation wizard with a vertical timeline where completed steps collapse to summary chips and the active step expands inline.

## Architecture

Single-file rewrite of `frontend/src/app/(dashboard)/chatbots/new/page.tsx`. No new components needed — the layout change is self-contained in JSX and Tailwind classes. Step state management stays identical (`useState<Step>`).

## Four Steps

| # | id | Label |
|---|-----|-------|
| 1 | `url` | Your website |
| 2 | `crawling` | Crawl & analyse |
| 3 | `review` | Review config |
| 4 | `done` | Go live |

## Step States

### Pending (not yet reached)
- Small circle with step number, gray border, gray text
- Label shown inline to the right, muted gray
- Not interactive

### Active (current step)
- Filled primary-500 circle with step number
- Full card to the right: white background, 2px primary-500 border, soft `ring-4 ring-primary-100` focus ring
- Card contains the full step UI (inputs, progress bars, review fields, embed code)
- Step 4 (`done`) is always the terminal active state — it never collapses to a chip

### Done (completed, collapsed)
- Filled primary-500 circle with white checkmark `✓`
- Compact green chip: `bg-green-50 border border-green-200 rounded-lg px-3 py-2`
- See **Step Summaries** below for chip text
- Steps 1 and 3 are clickable (cursor-pointer, faint `edit ✎` hint on hover)
- Step 2 is **never clickable**

### Step 2 — error / incomplete states
Step 2 stays **expanded** (never collapses to a chip) when it ends in any of these states:
- `crawlStatus.stalled === true` — shows the existing stalled UI (amber alert, "Start over" button)
- `autoconfigError !== ""` — shows the existing autoconfig-error UI (amber alert, "Retry" + "Start over" buttons)
- `crawlStatus.status === "failed"` — the existing code already resets the step to `"url"` in this case; the timeline simply returns to step 1 as the active step, with step 2 no longer rendered as done (it never completed)

In the stalled and autoconfigError cases the step 2 circle turns amber-500 instead of primary-500.

## Spine

- A 2px vertical line connects each circle to the next
- **primary-500** when the segment connects two *successfully completed* steps
- **gray-200** in all other cases (pending, active, or errored step 2)

## Step Summaries (collapsed chip text)

| Step | Chip text |
|------|-----------|
| 1 — Your website | `{hostname} · {botName}` |
| 2 — Crawl & analyse | `{docs_indexed} pages indexed · AI config ready` |
| 3 — Review config | `{reviewName} · {tone} · {language}` |

Step 4 has no collapsed chip — it is always the active terminal state.

## Layout

- Same `max-w-2xl mx-auto` container as today
- Each step row: `flex gap-3.5`, spine column (fixed 26px wide) + content column (`flex-1`)
- Spine column: `flex flex-col items-center` — circle + line
- Content column: chip or expanded card + bottom padding (`pb-2`) to space from next step

## Back-navigation Interaction

**Clicking the step 1 chip:**
- Only enabled when step 2 has *successfully* completed (chip is shown). If step 2 is still polling or in an error state, the step 1 chip is not clickable.
- Clicking reopens step 1 with an amber border and `ring-4 ring-amber-100`
- An amber warning banner appears inside the card: *"Changing the URL will restart the crawl and discard the current config."*
- Steps 2, 3, and 4 dim to 40% opacity
- Two buttons: **Cancel** (collapses step 1 back to chip, restores normal opacity) and **Restart with new URL →** (resets all downstream state — `crawlStatus`, `crawlJobId`, `crawlKbId`, `autoconfigRunning`, `autoconfigError`, `config`, `chatbotId`, and all review fields — and sets step back to `"url"`)

**Clicking the step 3 chip:**
- Only enabled when step 3 has already been saved (i.e. `chatbotId` is set and step 4 is active). `chatbotId` is guaranteed to be set at this point — it was created during `handleStart`.
- Reopens step 3 with the review fields populated from current state
- No warning needed — review field edits do not affect the crawl
- Step 4 dims to 40% opacity
- **Cancel** collapses step 3 back to chip; **Save & finish** calls the existing `handleSave()` path (calls `updateChatbot`, then advances to step 4)

## What Does NOT Change

- All step content (form fields, progress bars, review fields, embed code, platform guides)
- API calls, polling logic, state variables
- Mobile behaviour: spine + chips stack naturally in a single column
