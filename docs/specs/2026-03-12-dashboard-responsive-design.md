# Dashboard Responsive Design

**Date:** 2026-03-12
**Status:** Approved

## Overview

Make the PulseLite dashboard fully responsive. Currently the layout is desktop-only — the sidebar is always 224px wide with no mobile handling. This spec covers all changes needed to support phones, tablets, and small laptops.

## Breakpoint

Single breakpoint: **`xl` (1280px)**

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
- CopilotPanel: add `hidden xl:flex` so it only shows at desktop widths

## Section 2: Page-Level Responsive Adaptations

### Dashboard overview

**File:** `frontend/src/app/(dashboard)/dashboard/page.tsx`

- KPI stat grid: `grid-cols-1 sm:grid-cols-2 xl:grid-cols-3`
- Any other fixed-column grids: apply same pattern

### Chatbots list

**File:** `frontend/src/app/(dashboard)/chatbots/page.tsx`

- Card grid: `grid-cols-1 sm:grid-cols-2 min-[1200px]:grid-cols-3` (replace current non-responsive base)

### Chatbot detail tabs

**File:** `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx`

- Tab row: add `overflow-x-auto scrollbar-none` so tabs scroll horizontally on small screens without wrapping or clipping

### Conversations page

**File:** `frontend/src/app/(dashboard)/conversations/page.tsx`

This page has the most significant layout change.

**Below 1280px — stacked push navigation:**
- List panel fills full width
- A `selectedId` state controls which "panel" is shown: `null` = list, `string` = detail
- When user taps a conversation row, `setSelectedId(id)` — detail view replaces list (CSS: `hidden` / `block` swap or translate)
- Detail view shows a `← Back` button in its header that calls `setSelectedId(null)`
- No structural change to the data fetching — just conditional rendering

**At 1280px+ — existing split-view unchanged**

### Intelligence pages

**Files:** `frontend/src/app/(dashboard)/intelligence/`

- Grids already have `sm:grid-cols-2 lg:grid-cols-3`; no changes needed beyond verifying padding at small sizes

### Settings pages

**Files:** `frontend/src/app/(dashboard)/settings/`

- Pages are mostly single-column already; audit padding/max-width and ensure `px-4 sm:px-6` on containers

### Chatbot new / onboarding

- Step indicator labels: already have `hidden sm:block`; verify layout holds at small sizes

## Section 3: What Is Not Changing

- No bottom navigation bar
- No icon-only collapsed sidebar state (pure drawer only)
- No changes to auth pages (already responsive)
- No changes to the widget embed or public chat endpoint
- Backend: zero changes

## Files to Modify

| File | Change |
|------|--------|
| `src/app/(dashboard)/layout.tsx` | Sidebar context, drawer logic, backdrop overlay |
| `src/components/layout/Sidebar.tsx` | Position classes, close-on-navigate |
| `src/components/layout/TopBar.tsx` | Hamburger button, hide labels on mobile |
| `src/app/(dashboard)/dashboard/page.tsx` | Responsive grid |
| `src/app/(dashboard)/chatbots/page.tsx` | Responsive grid base |
| `src/app/(dashboard)/chatbots/[id]/layout.tsx` | Scrollable tabs |
| `src/app/(dashboard)/conversations/page.tsx` | Push navigation below xl |
| `src/app/(dashboard)/settings/*.tsx` | Padding audit |

## Testing

- Resize browser to 375px, 768px, 1024px, 1280px, 1440px and verify layout at each
- Conversations: verify list→detail→back flow works at mobile width
- Sidebar: verify drawer opens/closes, backdrop dismisses, route change closes it
- TopBar: verify hamburger visible below xl, hidden at xl+
