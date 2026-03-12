# Dashboard Responsive Design

**Date:** 2026-03-12
**Status:** Approved

## Overview

Make the PulseLite dashboard fully responsive. Currently the layout is desktop-only — the sidebar is always 224px wide with no mobile handling. This spec covers all changes needed to support phones, tablets, and small laptops.

## Breakpoint

Single primary breakpoint: **`xl` (1280px)** governs structural layout (sidebar, split-views).

`sm` (640px) is used for cosmetic label visibility only (topbar labels, button text) — it does not affect structural layout.

The chatbots grid retains its existing `min-[1200px]` breakpoint as a deliberate exception to the `xl` rule (grid-only, not layout-structural).

- Below 1280px → mobile/tablet mode (drawer sidebar, stacked layouts)
- 1280px and above → desktop mode (full sidebar, split layouts)

## Section 1: Shell & Layout System

### Sidebar

**File:** `frontend/src/components/layout/Sidebar.tsx`
**File:** `frontend/src/app/(dashboard)/layout.tsx`

- Introduce a `useSidebar` context (or simple useState in layout) that tracks `isOpen: boolean` with a `toggle()` function
- Pass `isOpen` and `toggle` down to Sidebar and TopBar via context or props
- **Below 1280px:** sidebar is `fixed inset-y-0 left-0 z-50 w-56`, hidden with `-translate-x-full`, visible with `translate-x-0`, transition `duration-200 ease-in-out`
- **At 1280px+:** sidebar renders in normal flow as today (`relative w-56 flex-shrink-0`)
- Add a backdrop overlay (`fixed inset-0 bg-black/40 z-40`) below 1280px when drawer is open; clicking it closes the drawer
- Close drawer on route change (add `useEffect` watching `location.pathname`)
- Note: the workspace switcher dropdown inside Sidebar already uses `z-50`; this is fine since it renders inside the sidebar which is also `z-50`

### TopBar

**File:** `frontend/src/components/layout/TopBar.tsx`

- Add hamburger button on the left, visible only below 1280px (`xl:hidden`), calls `toggle()`
- Search button: hide text label below `sm` (`hidden sm:inline`), show icon always
- `+ New` action button: hide label text below `sm`, show icon always (`sm:hidden` on the label span)
- Breadcrumb: truncate with `truncate max-w-[160px] sm:max-w-none` to prevent overflow

### Layout wrapper

**File:** `frontend/src/app/(dashboard)/layout.tsx`

- Sidebar always rendered in DOM; position/transform controls visibility
- Main content area does not shift on drawer open (overlay pattern, not push pattern)
- CopilotPanel: wrap the call site in `<div className="hidden xl:flex">` in layout.tsx (CopilotPanel itself renders a fragment, so the responsive class must live on a wrapper div at the call site, not inside CopilotPanel)

## Section 2: Page-Level Responsive Adaptations

### Dashboard overview

**File:** `frontend/src/app/(dashboard)/dashboard/page.tsx`

Three grids need responsive classes:

1. **KPI stat grid** (`grid grid-cols-3`) → `grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3`
2. **Second grid** (`grid grid-cols-2`) → `grid grid-cols-1 sm:grid-cols-2`
3. **Third grid** (`grid grid-cols-2`) → `grid grid-cols-1 sm:grid-cols-2`

### Chatbots list

**File:** `frontend/src/app/(dashboard)/chatbots/page.tsx`

- Card grid: `grid-cols-1 sm:grid-cols-2 min-[1200px]:grid-cols-3`
- The `min-[1200px]` is a deliberate exception to the `xl` rule — it was pre-existing and governs grid columns only, not layout structure. Do not change it to `xl:grid-cols-3`.

### Chatbot detail tabs

**File:** `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx`

- The tab `<nav className="flex gap-6">` element (not the outer `<div className="border-b ...">`) gets `overflow-x-auto scrollbar-none`
- The outer border-b div stays full-width; only the nav scrolls internally

### Conversations page

**File:** `frontend/src/app/(dashboard)/conversations/page.tsx`

This page has the most significant layout change.

**Below 1280px — stacked push navigation (URL-driven):**

- `selectedId` is already derived from `useSearchParams` — keep this as the source of truth
- Panel visibility is driven by `selectedId !== null` (from URL), not a separate useState
- List panel: shown when `selectedId` is null OR on xl+; hidden on mobile when `selectedId` is set
- Detail panel: shown when `selectedId` is set OR on xl+; hidden on mobile when `selectedId` is null
- Back button in detail header calls `navigate('/conversations', { replace: true })` to clear the `?id=` param
- The `showMeta` right panel (`w-[180px]`, toggled by "Show info / Hide info"): **hidden by default on mobile** (`hidden xl:block`). The "Show info" toggle button is also hidden below xl. This prevents the 180px panel from collapsing the message area on small screens.

**At 1280px+ — existing split-view unchanged**

### Intelligence pages

**Files:** `frontend/src/app/(dashboard)/intelligence/`

- Grids already have `sm:grid-cols-2 lg:grid-cols-3`; no changes needed beyond verifying padding at small sizes

### Settings pages

**Files:** `frontend/src/app/(dashboard)/settings/`

Pages to audit (7 files): `page.tsx`, `team/page.tsx`, `billing/page.tsx`, `integrations/page.tsx`, `llm/page.tsx`, `security/page.tsx`, `data-retention/page.tsx`, `webhooks/page.tsx`

- Pages are mostly single-column already; ensure outer container has `px-4 sm:px-6` (not fixed `px-8` or wider) so content doesn't clip on small screens

### Chatbot new / onboarding

- Step indicator labels: already have `hidden sm:block`; verify layout holds at small sizes — no changes expected

## Section 3: What Is Not Changing

- No bottom navigation bar
- No icon-only collapsed sidebar state (pure drawer only)
- No changes to auth pages (already responsive)
- No changes to the widget embed or public chat endpoint
- No accessibility focus-trap in drawer (out of scope; Escape key to close is a nice-to-have, not required)
- Backend: zero changes

## Files to Modify

| File | Change |
|------|--------|
| `src/app/(dashboard)/layout.tsx` | Sidebar context, drawer logic, backdrop overlay, CopilotPanel wrapper div |
| `src/components/layout/Sidebar.tsx` | Position classes, close-on-navigate |
| `src/components/layout/TopBar.tsx` | Hamburger button, hide labels on mobile |
| `src/app/(dashboard)/dashboard/page.tsx` | All 3 grids responsive |
| `src/app/(dashboard)/chatbots/page.tsx` | Add `grid-cols-1` base |
| `src/app/(dashboard)/chatbots/[id]/layout.tsx` | `overflow-x-auto` on `<nav>` element |
| `src/app/(dashboard)/conversations/page.tsx` | URL-driven push nav below xl; showMeta hidden below xl |
| `src/app/(dashboard)/settings/*.tsx` | Padding audit (8 files) |

## Testing

- Resize browser to 375px, 768px, 1024px, 1280px, 1440px and verify layout at each
- Conversations: verify list→detail→back flow at mobile; confirm URL updates on each transition
- Sidebar: verify drawer opens/closes, backdrop dismisses, route change closes it
- TopBar: verify hamburger visible below xl, hidden at xl+
- CopilotPanel: verify hidden below xl, visible at xl+
- Settings: verify no horizontal scroll or clipped content at 375px
