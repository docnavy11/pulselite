# Chatbot Creation Wizard — Vertical Timeline Redesign

## Goal

Replace the horizontal progress bar at the top of the chatbot creation wizard with a vertical timeline where completed steps collapse to summary chips and the active step expands inline.

## Architecture

Single-file rewrite of `frontend/src/app/(dashboard)/chatbots/new/page.tsx`. No new components needed — the layout change is self-contained in JSX and Tailwind classes. Step state management stays identical (`useState<Step>`).

## Step States

### Pending (not yet reached)
- Small circle with step number, gray border, gray text
- Label shown inline to the right, muted gray
- Not interactive

### Active (current step)
- Filled primary-500 circle with step number
- Full card to the right: white background, 2px primary-500 border, soft primary-100 focus ring (`ring-4 ring-primary-100`)
- Card contains the full step UI (inputs, progress bars, review fields, embed code)

### Done (completed, collapsed)
- Filled primary-500 circle with white checkmark
- Compact green chip to the right: `bg-green-50 border border-green-200`, showing a one-line summary of what was entered/achieved
- Step 1 chip: shows `{domain} · {botName}` — has `cursor-pointer` and a faint `edit ✎` hint, clickable to reopen
- Step 2 chip: shows `{N} pages indexed · AI config ready` — **not clickable** (nothing to edit in an automated step)
- Step 3 chip (after save): shows `{reviewName} · {tone}` — clickable to reopen

### Done (expanded — user clicked back)
- Circle turns amber-500
- Card reopens with amber border and amber focus ring
- **Step 1 only**: shows an amber warning banner — "Changing the URL will restart the crawl and discard the current config." — plus Cancel and "Restart with new URL →" buttons. Downstream steps (2, 3, 4) dim to 40% opacity.
- **Step 3 only**: reopens review fields normally. No warning needed — changing review fields doesn't affect the crawl.

## Spine

- A 2px vertical line connects each circle to the next
- Line colour: primary-500 if the segment connects two completed steps, gray-200 otherwise
- Line grows from the bottom of each circle to the top of the next

## Layout

- Same max-w-2xl mx-auto container as today
- Each step row: `flex gap-3.5`, spine column (fixed 26px wide) + content column (flex-1)
- Spine column: circle + line, `flex flex-col items-center`
- Content column: chip or expanded card + bottom padding to space from next step

## Interaction Rules

1. Clicking a **done chip** for step 1 or step 3 → expands that step, collapses the current active step back to its chip (or leaves it as-is if it hasn't been completed yet — this shouldn't happen in normal flow since you can only go back from a later step)
2. Clicking **Cancel** in an expanded-back step → collapses it again, active step resumes
3. Submitting step 1 again after clicking back → resets step, crawl, review, and done state; restarts from crawl
4. Step 2 chip is not clickable

## Step Summaries (collapsed chip text)

| Step | Summary text |
|------|-------------|
| 1 — Your website | `{hostname} · {botName}` |
| 2 — Crawl & analyse | `{docs_indexed} pages indexed · AI config ready` (or error state if failed) |
| 3 — Review config | `{reviewName} · {tone}` |

## What Does NOT Change

- All step content (form fields, progress bars, review fields, embed code, platform guides) stays identical
- API calls, polling logic, state variables — unchanged
- Mobile behaviour: spine + chips stack naturally in single column, same as today
