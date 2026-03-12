# Dashboard Responsive Design Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the PulseLite dashboard fully responsive using a single `xl` (1280px) breakpoint — hamburger+drawer sidebar on mobile/tablet, push-navigation for conversations, and responsive grids throughout.

**Architecture:** Sidebar becomes a fixed overlay drawer below xl and returns to normal flow at xl+. A `sidebarOpen` boolean in `DashboardShell` is passed as props to `<Sidebar>` and `<TopBar>`. All layout changes are pure Tailwind CSS — no new libraries, no JS media query hooks.

**Tech Stack:** React 19, React Router v7, Tailwind CSS v3, Vite

**Spec:** `docs/specs/2026-03-12-dashboard-responsive-design.md`

---

## Chunk 1: Shell — Layout, Sidebar, TopBar

### Task 1: Update `layout.tsx` — sidebar state, backdrop, CopilotPanel wrapper

**Files:**
- Modify: `frontend/src/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Open the file and understand the current structure**

  Current `DashboardShell` renders `<Sidebar />`, `<TopBar />`, and `<CopilotPanel />` with no responsive classes. Goal: add `sidebarOpen` state, backdrop overlay, and pass props down.

- [ ] **Step 2: Replace `layout.tsx` with the responsive version**

  ```tsx
  import { useState, useCallback } from 'react'
  import { Outlet } from 'react-router-dom'
  import { Sidebar } from "@/components/layout/Sidebar";
  import { TopBar } from "@/components/layout/TopBar";
  import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
  import { CommandPalette } from "@/components/CommandPalette";
  import { ToastProvider } from "@/components/ui/Toast";
  import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
  import { CopilotProvider } from "@/components/copilot/CopilotProvider";
  import { CopilotPanel } from "@/components/copilot/CopilotPanel";

  function DashboardShell() {
    useKeyboardShortcuts();
    const [sidebarOpen, setSidebarOpen] = useState(false);
    // Stable reference so Sidebar's useEffect dep array doesn't re-fire on every render
    const closeSidebar = useCallback(() => setSidebarOpen(false), []);

    return (
      <ProtectedRoute>
        <div className="flex h-screen overflow-hidden">
          {/* Backdrop — mobile/tablet only, dismisses drawer */}
          {sidebarOpen && (
            <div
              className="fixed inset-0 bg-black/40 z-40 xl:hidden"
              onClick={closeSidebar}
            />
          )}
          <Sidebar isOpen={sidebarOpen} onClose={closeSidebar} />
          <div className="flex flex-1 flex-col overflow-hidden">
            <TopBar onMenuToggle={() => setSidebarOpen((o) => !o)} />
            <div className="flex flex-1 overflow-hidden">
              <main className="flex-1 overflow-auto bg-[#faf8f5] p-6">
                <Outlet />
              </main>
              {/* CopilotPanel hidden below xl */}
              <div className="hidden xl:flex">
                <CopilotPanel />
              </div>
            </div>
          </div>
        </div>
        <CommandPalette />
        <ToastProvider />
      </ProtectedRoute>
    );
  }

  export default function DashboardLayout() {
    return (
      <CopilotProvider>
        <DashboardShell />
      </CopilotProvider>
    );
  }
  ```

- [ ] **Step 3: Verify TypeScript compiles**

  ```bash
  docker compose exec frontend npx tsc --noEmit 2>&1 | head -30
  ```
  Expected: errors only in Sidebar.tsx and TopBar.tsx (props not yet updated) — no errors in layout.tsx itself.

---

### Task 2: Update `Sidebar.tsx` — drawer behaviour

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add `isOpen` and `onClose` props + close-on-navigate effect**

  At the top of the `Sidebar` function, add the props interface and a useEffect:

  ```tsx
  interface SidebarProps {
    isOpen: boolean;
    onClose: () => void;
  }

  export function Sidebar({ isOpen, onClose }: SidebarProps) {
    const { pathname } = useLocation();
    // ... existing state ...

    // Close drawer on any route change (mobile)
    // Include onClose in deps — it must be wrapped in useCallback in layout.tsx (see Task 1)
    useEffect(() => {
      onClose();
    }, [pathname, onClose]);

    // ... rest of existing code unchanged ...
  ```

- [ ] **Step 2: Replace the `<aside>` opening class**

  Old:
  ```tsx
  <aside className="flex h-screen w-56 flex-col bg-white border-r border-[#f0ebe3] flex-shrink-0">
  ```

  New:
  ```tsx
  <aside className={clsx(
    "flex h-screen w-56 flex-col bg-white border-r border-[#f0ebe3]",
    // Below xl: fixed overlay, slides in/out
    "fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-in-out",
    // At xl+: back to normal document flow
    "xl:static xl:z-auto xl:flex-shrink-0 xl:translate-x-0",
    // Open/closed (only meaningful below xl — xl:translate-x-0 overrides)
    isOpen ? "translate-x-0" : "-translate-x-full",
  )}>
  ```

- [ ] **Step 3: Verify TypeScript compiles**

  ```bash
  docker compose exec frontend npx tsc --noEmit 2>&1 | head -30
  ```
  Expected: no errors in Sidebar.tsx. TopBar.tsx may still have a prop error.

- [ ] **Step 4: Visual check — sidebar drawer**

  Open http://localhost:3001 in browser and resize to 900px wide. Sidebar should be hidden. Resize to 1400px — sidebar should appear. (Hamburger not yet added so you can't open the drawer yet — that's fine.)

---

### Task 3: Update `TopBar.tsx` — hamburger + mobile label hiding

**Files:**
- Modify: `frontend/src/components/layout/TopBar.tsx`

- [ ] **Step 1: Add `onMenuToggle` prop and hamburger button**

  Replace the entire file:

  ```tsx
  import { useLocation, useNavigate } from "react-router-dom";
  import { IconBell, IconPlus, IconSearch } from "@/components/icons/NavIcons";
  import { Breadcrumb } from "@/components/ui/Breadcrumb";

  interface TopBarProps {
    onMenuToggle: () => void;
  }

  const NEW_BUTTON_ACTIONS: Record<string, { label: string; href: string }> = {
    "/chatbots":      { label: "New chatbot",  href: "/chatbots/new" },
    "/conversations": { label: "Export",       href: "/conversations" },
    "/intelligence":  { label: "Add source",   href: "/intelligence" },
  };

  export function TopBar({ onMenuToggle }: TopBarProps) {
    const { pathname } = useLocation();
    const navigate = useNavigate();

    const action = NEW_BUTTON_ACTIONS[pathname] ?? { label: "New chatbot", href: "/chatbots/new" };

    const openCommandPalette = () => {
      window.dispatchEvent(new CustomEvent("open-command-palette"));
    };

    return (
      <header className="h-12 flex items-center gap-3 px-5 bg-white border-b border-[#f0ebe3] flex-shrink-0">
        {/* Hamburger — hidden at xl+ */}
        <button
          onClick={onMenuToggle}
          className="xl:hidden p-1.5 -ml-1.5 rounded-lg hover:bg-[#faf8f5] transition-colors"
          aria-label="Open menu"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 4h12M2 8h12M2 12h12" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>

        {/* Left: breadcrumb — truncate wrapper prevents overflow on small screens */}
        <div className="flex-1 min-w-0 truncate max-w-[160px] sm:max-w-none">
          <Breadcrumb />
        </div>

        {/* Centre-right: ⌘K trigger */}
        <button
          onClick={openCommandPalette}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#faf8f5] border border-[#f0ebe3] text-gray-400 hover:border-[#e0dbd2] hover:text-gray-600 transition-colors text-[11px]"
        >
          <IconSearch size={11} className="stroke-gray-400" />
          <span className="hidden sm:inline">Search…</span>
          <kbd className="hidden sm:inline ml-1 text-[9px] font-medium bg-white border border-[#e8e2d8] rounded px-1 py-0.5 text-gray-400">⌘K</kbd>
        </button>

        {/* Bell */}
        <button className="p-1.5 rounded-lg hover:bg-[#faf8f5] transition-colors">
          <IconBell size={14} className="stroke-gray-400" />
        </button>

        {/* + New */}
        <button
          onClick={() => navigate(action.href)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg text-[11px] font-semibold transition-colors"
        >
          <IconPlus size={11} className="stroke-white" />
          <span className="hidden sm:inline">{action.label}</span>
        </button>
      </header>
    );
  }
  ```

- [ ] **Step 2: Verify TypeScript compiles cleanly**

  ```bash
  docker compose exec frontend npx tsc --noEmit 2>&1 | head -30
  ```
  Expected: no errors.

- [ ] **Step 3: Visual check — shell at all breakpoints**

  Open http://localhost:3001. Resize the browser window and verify:
  - **375px**: Hamburger visible, breadcrumb shows, search icon only, + New icon only
  - **640px**: Search "Search…" text appears, + New label appears
  - **1280px+**: Hamburger hidden, full sidebar visible in normal flow
  - Tap hamburger at narrow width → sidebar slides in from left
  - Tap backdrop → sidebar closes
  - Navigate to another page → sidebar closes

- [ ] **Step 4: Commit Chunk 1**

  ```bash
  git add frontend/src/app/\(dashboard\)/layout.tsx \
          frontend/src/components/layout/Sidebar.tsx \
          frontend/src/components/layout/TopBar.tsx
  git commit -m "feat: responsive sidebar drawer and topbar hamburger (xl breakpoint)"
  ```

---

## Chunk 2: Conversations Push Navigation

### Task 4: Update `conversations/page.tsx` — URL-driven mobile push nav

**Files:**
- Modify: `frontend/src/app/(dashboard)/conversations/page.tsx`

The page already uses `useSearchParams` for `selectedId`. We drive panel visibility entirely from the URL — no new state needed.

- [ ] **Step 1: Update the list panel div (line 132)**

  Old:
  ```tsx
  <div className="w-[280px] flex-shrink-0 flex flex-col bg-white border-r border-[#f0ebe3]">
  ```

  New — full width on mobile, fixed 280px at xl; hidden on mobile when a conversation is selected:
  ```tsx
  <div className={clsx(
    "flex-col bg-white border-r border-[#f0ebe3]",
    "xl:w-[280px] xl:flex-shrink-0 xl:flex",
    selectedId ? "hidden xl:flex" : "flex w-full",
  )}>
  ```

- [ ] **Step 2: Update the detail panel div (line 223)**

  Old:
  ```tsx
  <div className="flex-1 flex overflow-hidden">
  ```

  New — hidden on mobile when no conversation selected; empty-state still visible at xl when nothing selected:
  ```tsx
  <div className={clsx(
    "overflow-hidden",
    selectedId ? "flex flex-1" : "hidden xl:flex xl:flex-1",
  )}>
  ```

- [ ] **Step 3: Add Back button to the detail header (line 242)**

  Inside the detail header `<div className="flex items-center gap-3 px-5 py-3 border-b border-[#f0ebe3] bg-white">`, add as the first child:

  ```tsx
  {/* Back button — mobile only */}
  <button
    onClick={() => navigate("/conversations", { replace: true })}
    className="xl:hidden flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-700 mr-1 flex-shrink-0"
  >
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path d="M8 2L4 6l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
    Back
  </button>
  ```

- [ ] **Step 4: Hide showMeta panel and its toggle below xl**

  The toggle button (line 267):

  Old:
  ```tsx
  <button
    onClick={() => setShowMeta((s) => !s)}
    className="text-[11px] text-gray-400 hover:text-gray-600"
  >
    {showMeta ? "Hide info" : "Show info"}
  </button>
  ```

  New — hidden below xl:
  ```tsx
  <button
    onClick={() => setShowMeta((s) => !s)}
    className="hidden xl:inline text-[11px] text-gray-400 hover:text-gray-600"
  >
    {showMeta ? "Hide info" : "Show info"}
  </button>
  ```

  The meta panel (line 304):

  Old:
  ```tsx
  {showMeta && (
    <div className="w-[180px] flex-shrink-0 border-l border-[#f0ebe3] bg-white overflow-y-auto px-4 py-4 space-y-4">
  ```

  New — hidden below xl even when showMeta is true:
  ```tsx
  {showMeta && (
    <div className="hidden xl:block w-[180px] flex-shrink-0 border-l border-[#f0ebe3] bg-white overflow-y-auto px-4 py-4 space-y-4">
  ```

- [ ] **Step 5: Verify TypeScript compiles**

  ```bash
  docker compose exec frontend npx tsc --noEmit 2>&1 | head -30
  ```
  Expected: no errors.

- [ ] **Step 6: Visual check — conversations at mobile width**

  Open http://localhost:3001/conversations. Resize to 375px and verify:
  - List fills full width, no detail panel visible
  - Tap a conversation → URL changes to `?id=...`, list hides, detail shows full width
  - "← Back" button visible in detail header
  - Tap "← Back" → URL clears, detail hides, list shows again
  - Resize to 1280px+ → split view restored, back button gone, "Hide info" toggle visible

- [ ] **Step 7: Commit Chunk 2**

  ```bash
  git add frontend/src/app/\(dashboard\)/conversations/page.tsx
  git commit -m "feat: conversations mobile push navigation (URL-driven, xl breakpoint)"
  ```

---

## Chunk 3: Page Grids and Tabs

### Task 5: Fix dashboard overview grids

**Files:**
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx`

- [ ] **Step 1: Fix KPI grid (find `grid grid-cols-3 gap-4 mb-6`)**

  Old:
  ```tsx
  <div className="grid grid-cols-3 gap-4 mb-6">
  ```

  New:
  ```tsx
  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
  ```

- [ ] **Step 2: Fix Satisfaction + Sentiment grid (find `grid grid-cols-2 gap-4 mb-6` — first occurrence after KPI row)**

  Old:
  ```tsx
  <div className="grid grid-cols-2 gap-4 mb-6">
  ```

  New:
  ```tsx
  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
  ```

  Note: there are two `grid grid-cols-2 gap-4 mb-6` in this file. Apply to both (Satisfaction+Sentiment row and Topics row).

- [ ] **Step 3: Fix Topics grid (find the second `grid grid-cols-2 gap-4 mb-6`)**

  Same change as Step 2.

- [ ] **Step 4: Visual check — dashboard at mobile width**

  Open http://localhost:3001/dashboard at 375px. Verify KPI cards stack to 1 column, charts/topics stack to 1 column on phone and 2 on sm+.

- [ ] **Step 5: Commit Task 5**

  ```bash
  git add frontend/src/app/\(dashboard\)/dashboard/page.tsx
  git commit -m "feat: responsive dashboard overview grids"
  ```

---

### Task 6: Fix chatbots list grid

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/page.tsx`

- [ ] **Step 1: Add `grid-cols-1` base to chatbots grid (line 82)**

  Old:
  ```tsx
  <div className="grid grid-cols-2 gap-4 min-[1200px]:grid-cols-3">
  ```

  New:
  ```tsx
  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 min-[1200px]:grid-cols-3">
  ```

- [ ] **Step 2: Visual check**

  Open http://localhost:3001/chatbots at 375px. Cards stack in 1 column. At 640px → 2 columns. At 1200px+ → 3 columns.

- [ ] **Step 3: Commit Task 6**

  ```bash
  git add frontend/src/app/\(dashboard\)/chatbots/page.tsx
  git commit -m "feat: responsive chatbots grid (1 col mobile, 2 sm, 3 at 1200px)"
  ```

---

### Task 7: Fix chatbot detail scrollable tabs

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx`

- [ ] **Step 1: Add overflow classes to the `<nav>` element (line 175)**

  Old:
  ```tsx
  <nav className="flex gap-6">
  ```

  New — overflow on the nav only, not the outer border-b div:
  ```tsx
  <nav className="flex gap-6 overflow-x-auto scrollbar-none">
  ```

  The outer `<div className="border-b border-gray-200 mb-6">` is unchanged — it stays full-width so the border spans the page.

- [ ] **Step 2: Visual check**

  Open any chatbot detail page (http://localhost:3001/chatbots/a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108) at 375px. The 6 tabs (Knowledge, Configure, Actions, Appearance, Test, Publish) should scroll horizontally without wrapping or clipping. The bottom border should still span full width.

- [ ] **Step 3: Commit Task 7**

  ```bash
  git add frontend/src/app/\(dashboard\)/chatbots/\[id\]/layout.tsx
  git commit -m "feat: scrollable chatbot detail tabs on mobile"
  ```

---

### Task 8: Settings pages padding audit

**Files:**
- Modify (if needed): `frontend/src/app/(dashboard)/settings/page.tsx`, `settings/team/page.tsx`, `settings/billing/page.tsx`, `settings/integrations/page.tsx`, `settings/llm/page.tsx`, `settings/security/page.tsx`, `settings/data-retention/page.tsx`, `settings/webhooks/page.tsx`

- [ ] **Step 1: Check each settings file for hardcoded wide padding**

  Open each of the 8 files and find the outermost container div. If it has `px-8` or `px-10` (or any fixed padding wider than `px-6`), replace with `px-4 sm:px-6`. If it already uses `px-4`, `px-6`, or responsive padding, no change needed.

  Run this to find candidates quickly:
  ```bash
  grep -n "px-8\|px-10\|px-12" frontend/src/app/\(dashboard\)/settings/**/*.tsx
  ```

- [ ] **Step 2: Apply fixes to any files found in Step 1**

  For each file with wide fixed padding, replace the outer container's padding class:
  ```tsx
  // Old (example):
  <div className="... px-8 ...">
  // New:
  <div className="... px-4 sm:px-6 ...">
  ```

- [ ] **Step 3: Visual check — settings at mobile width**

  Open http://localhost:3001/settings at 375px. Verify no horizontal scroll. Check at least 3 settings sub-pages (General, Billing, Team).

- [ ] **Step 4: Commit Task 8**

  ```bash
  git add frontend/src/app/\(dashboard\)/settings/
  git commit -m "fix: settings pages padding responsive (px-4 sm:px-6)"
  ```

---

## Chunk 4: Final Verification

### Task 9: Full regression check

- [ ] **Step 1: Run frontend unit tests**

  ```bash
  make test-frontend
  ```
  Expected: all tests pass. These tests don't test layout classes but will catch any TypeScript or import errors introduced.

- [ ] **Step 2: Run e2e tests**

  ```bash
  make test-e2e
  ```
  Expected: all Playwright tests pass. The e2e suite runs at default viewport; confirm no regressions in existing flows.

- [ ] **Step 3: Manual responsive sweep**

  Open http://localhost:3001 and walk through each breakpoint. Use browser devtools responsive mode:

  | Width | Check |
  |-------|-------|
  | 375px (iPhone SE) | Hamburger visible, sidebar hidden, single-column grids, conversations list-only |
  | 640px (sm) | Search/+ New labels appear |
  | 768px (tablet portrait) | All still mobile-mode (sidebar drawer) |
  | 1024px | Still mobile-mode |
  | 1279px | Still mobile-mode (one pixel before xl) |
  | 1280px | Sidebar snaps into normal flow, hamburger gone |
  | 1440px | Desktop layout unchanged from before |

  Pages to check: Dashboard, Chatbots list, one Chatbot detail (tabs), Conversations (list→detail→back), Settings (General, Billing, Team).

- [ ] **Step 4: Final commit (if any fixes applied)**

  If any visual fixes were needed during the sweep, commit them:
  ```bash
  git add -p
  git commit -m "fix: responsive layout sweep adjustments"
  ```
