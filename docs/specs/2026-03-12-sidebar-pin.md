# Sidebar Pin & Collapsible Rail

**Date:** 2026-03-12
**Status:** Approved

## Overview

Add a pin/unpin toggle to the dashboard sidebar. On desktop (≥1280px) the sidebar collapses to an icon-only rail when unpinned. On mobile/tablet (<1280px) pinning suppresses the auto-close-on-navigate behaviour of the drawer.

## Pin State

A single boolean `sidebarPinned` (default: `true`) is owned by `DashboardShell` in `layout.tsx`. It is initialised from `localStorage` key `sidebar-pinned` on mount, and written back whenever it changes.

```ts
// Read on mount
const stored = localStorage.getItem('sidebar-pinned');
const initial = stored === null ? true : stored === 'true';

// Write on change (useEffect watching pinned)
localStorage.setItem('sidebar-pinned', String(pinned));
```

Default is `true` (pinned/expanded) in both desktop and mobile when `localStorage` is empty.

## Updated SidebarProps Interface

```ts
interface SidebarProps {
  isOpen: boolean;       // existing
  onClose: () => void;   // existing
  pinned: boolean;       // new
  onPinToggle: () => void; // new
}
```

## Behaviour

### Desktop (xl+, ≥1280px)

| State | Sidebar width | Content visible |
|-------|--------------|-----------------|
| Pinned (default) | `w-56` (224px) | Logo, workspace switcher, nav labels, settings sub-nav, copilot button, user footer |
| Unpinned | `w-10` (40px) | Main nav icons only; Settings icon only (no chevron, no sub-items) |

- The sidebar remains in normal document flow (`xl:static`) in both states — it pushes the main content area.
- Width transition: replace the existing `transition-transform duration-200 ease-in-out` on the `<aside>` with `transition-[width,transform] duration-200 ease-in-out`. This preserves the mobile slide-in/out transform animation while adding the desktop width collapse animation. Using two separate `transition-*` utilities would cause one to override the other in CSS.
- No hover-to-expand on the icon rail. The user clicks the pin button to re-expand.

**Icon-rail layout (unpinned on desktop):**
- Each nav link switches to `justify-center` with no label text and no gap.
- The Settings entry renders as a plain icon button (`<button>` with centered `<IconSettings>`), with no `<IconChevronDown>`, no label, no sub-items. The `settingsOpen` state is forced to `false` when `pinned` becomes `false` (to prevent hidden sub-items remaining in the expanded state when the sidebar re-expands).
- Workspace switcher, copilot button, and user footer are hidden (not rendered) in rail mode.
- Copilot is still accessible via the ⌘J keyboard shortcut (handled by a `keydown` listener in `CopilotProvider.tsx`), which remains functional whether or not the copilot button is visible.

### Mobile/tablet (<1280px)

`sidebarPinned` defaults to `true` — so pinned is the default on mobile too (drawer does not auto-close). If the user unpins from desktop, mobile also stops auto-closing.

| `pinned` value | Auto-close on navigate |
|----------------|------------------------|
| `true` (default) | No — drawer stays open across navigation |
| `false` | Yes — drawer closes on every route change |

- The backdrop and hamburger button always close the drawer regardless of `pinned`.
- The `useEffect` in `Sidebar.tsx` that watches `pathname`:

```ts
useEffect(() => {
  if (!pinned) onClose();
}, [pathname, pinned, onClose]);
```

`pinned` must be included in the dependency array to satisfy the `react-hooks/exhaustive-deps` rule.

## Pin Button

- **Appearance:** push-pin SVG icon. Filled/coloured (`text-primary-500`) when pinned; outline/grey (`text-gray-300`) when unpinned.
- **Position:** Rendered on desktop only (`hidden xl:flex`). On mobile the pin state still applies (persisted via localStorage) but there is no toggle button in the drawer — the state is controlled from desktop.
- **Accessibility:** `aria-label="Pin sidebar"` when unpinned; `aria-label="Unpin sidebar"` when pinned.

**Header layout in expanded mode (pinned):** logo mark + "pulse" text on the left, pin button on the right — both on the same row.

**Header layout in rail mode (unpinned):** only the pin button is shown, centered in the 40px rail. The logo mark, "pulse" text, and workspace switcher are hidden (`hidden` when `!pinned`). This is the only interactive element in the header when in rail mode.

## Files to Modify

| File | Change |
|------|--------|
| `src/app/(dashboard)/layout.tsx` | Add `sidebarPinned` state (localStorage-backed, default `true`); persist to localStorage on change; pass `pinned` and `onPinToggle` to `<Sidebar>` |
| `src/components/layout/Sidebar.tsx` | Accept new props; add `transition-[width]` and conditional `w-10`/`w-56` to `<aside>` via clsx; render icon-rail layout using Tailwind breakpoint classes (`xl:hidden` on labels, conditional rendering of sections based on `pinned` prop); add pin button to header; update `useEffect` dep array |

**Implementation note — no JS media query needed:** All rail-vs-full layout differences are handled via the `pinned` prop combined with existing Tailwind `xl:` classes. There is no `isDesktop` boolean or `useMediaQuery` hook — the `pinned` prop alone drives which elements render, and `xl:` prefixes handle any remaining breakpoint-specific overrides (e.g., the pin button is `hidden xl:flex`).

## What Is Not Changing

- No hover-to-expand on the icon rail.
- No icon-only mode on mobile (the drawer, when open, is always full-width w-56).
- No changes to TopBar, CopilotPanel, or any page components.
- No backend changes.

## Testing

- Desktop pinned (default): sidebar is 224px, all labels and sections visible.
- Desktop unpinned: sidebar is 40px, icons only, smooth width transition.
- Settings in rail mode: icon only, no chevron, no sub-items.
- Pin button fills/colours when pinned; outline when unpinned.
- Pin state survives page refresh (localStorage).
- Mobile pinned (default): navigating does not close drawer; backdrop and hamburger still close it.
- Mobile unpinned: navigating closes drawer.
- ⌘J opens Copilot when sidebar is in rail mode (no copilot button visible).
