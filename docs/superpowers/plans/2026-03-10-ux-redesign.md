# UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the PulseLite frontend from a generic dark-sidebar SaaS into a Warm Studio aesthetic with custom SVG glyphs, split-pane conversations, command palette, butter-smooth micro-interactions, and clear first-time UX.

**Architecture:** All changes are purely frontend (Next.js 15 App Router). The foundation (accent colour + icon system) must land first; subsequent chunks are independent and can run in parallel. No backend changes required.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS, Zustand, Recharts, `cmdk` (command palette), `react-hot-toast` (toasts).

**Design spec:** `docs/superpowers/specs/2026-03-10-ux-redesign-design.md`

---

## File Map

| File | Action | Responsible for |
|---|---|---|
| `frontend/tailwind.config.ts` | Modify | Replace indigo `primary` palette with warm orange `#ff6b35` |
| `frontend/src/app/globals.css` | Modify | Add warm CSS variables, sidebar light theme vars |
| `frontend/src/components/icons/NavIcons.tsx` | **Create** | Custom SVG glyphs for all nav items (inline, 16×16) |
| `frontend/src/components/layout/Sidebar.tsx` | Rewrite | Warm sidebar, 5 top-level items, collapsed settings, workspace switcher, user footer |
| `frontend/src/components/layout/TopBar.tsx` | Rewrite | ⌘K trigger, breadcrumbs, notification bell, context + button |
| `frontend/src/components/CommandPalette.tsx` | **Create** | ⌘K global search/navigate using `cmdk` |
| `frontend/src/components/ui/Toast.tsx` | **Create** | Bottom-right toast notification system |
| `frontend/src/components/ui/Skeleton.tsx` | **Create** | Reusable skeleton loading block |
| `frontend/src/components/ui/Breadcrumb.tsx` | **Create** | Route-aware breadcrumb component |
| `frontend/src/app/(dashboard)/layout.tsx` | Modify | Mount CommandPalette + Toast provider |
| `frontend/src/app/(dashboard)/dashboard/page.tsx` | Rewrite | Greeting, quick actions, activity feed, empty state, skeleton |
| `frontend/src/app/(dashboard)/conversations/page.tsx` | Rewrite | Split-pane: list + slide-over + metadata sidebar |
| `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx` | Modify | New tab order + icons: Knowledge → Configure → Actions → Appearance → Test → Publish |
| `frontend/src/app/(dashboard)/chatbots/[id]/sources/SourcesTab.tsx` | Modify | Hover actions, retry-on-fail, bulk select, remove Chunks column |
| `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx` | Modify | Sectioned form, sticky save, mobile preview toggle |
| `frontend/src/app/(dashboard)/chatbots/[id]/deploy/page.tsx` | Rename to `publish/page.tsx` | Keep existing embed code content, add go-live toggle |
| `frontend/src/app/(dashboard)/chatbots/[id]/chat/page.tsx` | Rename references to `test` | Keep existing chat test content |
| `frontend/src/lib/toast.ts` | **Create** | `useToast()` hook wrapping react-hot-toast |

---

## Chunk 1: Foundation — Accent Colour + Icon System

### Task 1: Replace primary colour palette

**Files:**
- Modify: `frontend/tailwind.config.ts`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Update Tailwind config**

Replace the `primary` colour scale and sidebar colours:

```ts
// frontend/tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        sidebar: {
          bg: "#ffffff",
          border: "#f0ebe3",
          text: "#777777",
          active: "#ff6b35",
          "active-bg": "#fff3ee",
          hover: "#faf8f5",
        },
        warm: {
          50: "#faf8f5",
          100: "#f5f0ea",
          200: "#f0ebe3",
          300: "#ede8e0",
        },
        primary: {
          50: "#fff3ee",
          100: "#ffe4d6",
          200: "#ffcbb8",
          300: "#ffa882",
          400: "#ff8552",
          500: "#ff6b35",
          600: "#e85a26",
          700: "#c44a1e",
          800: "#9e3c18",
          900: "#7a2e12",
        },
      },
    },
  },
  plugins: [],
};
export default config;
```

- [ ] **Step 2: Update globals.css**

```css
/* frontend/src/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #faf8f5;
  --foreground: #1a1a1a;
  --accent: #ff6b35;
  --accent-light: #fff3ee;
  --border-warm: #f0ebe3;
  --border-warm-strong: #ede8e0;
}

body {
  color: var(--foreground);
  background: var(--background);
}
```

- [ ] **Step 3: Global find-and-replace accent classes**

Run these replacements across all `frontend/src/` files:
```bash
# In frontend/src directory:
# primary-600 → primary-500 (our new 500 is the main orange)
# bg-indigo-* → bg-primary-*  (if any raw indigo used)
# text-indigo-* → text-primary-*
# border-indigo-* → border-primary-*
# focus:ring-primary-500 stays (already correct token)
```

Use VSCode find-replace or:
```bash
cd frontend/src
grep -rl "primary-600" . | xargs sed -i '' 's/primary-600/primary-500/g'
grep -rl "indigo-" . | xargs sed -i '' 's/indigo-/primary-/g'
```

- [ ] **Step 4: Verify app still renders**
```bash
cd frontend && npm run dev
# Open http://localhost:3001 — should see orange accent instead of indigo
```

- [ ] **Step 5: Commit**
```bash
git add frontend/tailwind.config.ts frontend/src/app/globals.css
git commit -m "feat: replace indigo accent with warm orange (#ff6b35)"
```

---

### Task 2: Create custom SVG icon system

**Files:**
- Create: `frontend/src/components/icons/NavIcons.tsx`

- [ ] **Step 1: Create the icon file**

```tsx
// frontend/src/components/icons/NavIcons.tsx
// Custom 16×16 SVG glyphs for navigation. stroke-linecap="round" stroke-linejoin="round" throughout.
// All icons accept className prop for colour/size overrides.

interface IconProps {
  className?: string;
  size?: number;
}

export function IconOverview({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path
        d="M1 8 L3.5 8 L5 4 L7 12 L9 6 L10.5 8 L15 8"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconChatbots({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path
        d="M8 1.5 L10 6 L14.5 8 L10 10 L8 14.5 L6 10 L1.5 8 L6 6 Z"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconConversations({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path
        d="M2 4 Q2 2 4 2 L12 2 Q14 2 14 4 L14 9 Q14 11 12 11 L9 11 L6 14 L7 11 L4 11 Q2 11 2 9 Z"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="5.5" cy="6.5" r="0.8" fill="currentColor" className="stroke-none" />
      <circle cx="8" cy="6.5" r="0.8" fill="currentColor" className="stroke-none" />
      <circle cx="10.5" cy="6.5" r="0.8" fill="currentColor" className="stroke-none" />
    </svg>
  );
}

export function IconIntelligence({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <circle cx="6" cy="8" r="4.5" strokeWidth="1.6" />
      <circle cx="10.5" cy="6.5" r="3.5" strokeWidth="1.6" />
    </svg>
  );
}

export function IconSettings({ className = "stroke-current", size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.5" strokeWidth="1.6" />
      <rect x="9"   y="1.5" width="5.5" height="5.5" rx="1.5" strokeWidth="1.6" />
      <rect x="1.5" y="9"   width="5.5" height="5.5" rx="1.5" strokeWidth="1.6" />
      <rect x="9"   y="9"   width="5.5" height="5.5" rx="1.5" strokeWidth="1.6" />
    </svg>
  );
}

// ── Tab icons (12×12) ──

export function IconKnowledge({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path d="M2 3 L10 3 M2 6 L8 6 M2 9 L6 9" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconConfigure({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path
        d="M6 1 L7.2 4.2 L10.5 5.5 L7.2 6.8 L6 10 L4.8 6.8 L1.5 5.5 L4.8 4.2 Z"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconActions({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <circle cx="6" cy="6" r="4.5" strokeWidth="1.4" />
      <path d="M6 3.5 L6 6 L8 6" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function IconAppearance({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <rect x="1.5" y="1.5" width="9" height="9" rx="2" strokeWidth="1.4" />
      <path
        d="M3.5 6 Q4.5 4.5 6 5.5 Q7.5 6.5 8.5 5"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconTest({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path
        d="M2 4 Q2 2 4 2 L8 2 Q10 2 10 4 L10 7 Q10 9 8 9 L7 9 L5 11 L5.5 9 L4 9 Q2 9 2 7 Z"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconPublish({ className = "stroke-current", size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" className={className}>
      <path
        d="M2 6 L5 9 L10 3"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── Utility icons ──

export function IconSearch({ className = "stroke-current", size = 14 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className}>
      <circle cx="6" cy="6" r="4" strokeWidth="1.5" />
      <path d="M9.5 9.5 L12.5 12.5" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconBell({ className = "stroke-current", size = 14 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className}>
      <path
        d="M7 2 C5.3 2 4 3.3 4 5 L4 8 L2.5 10 L11.5 10 L10 8 L10 5 C10 3.3 8.7 2 7 2 Z"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M5.5 10 C5.5 10.8 6.2 11.5 7 11.5 C7.8 11.5 8.5 10.8 8.5 10" strokeWidth="1.4" />
    </svg>
  );
}

export function IconPlus({ className = "stroke-current", size = 14 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className}>
      <path d="M7 2 L7 12 M2 7 L12 7" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function IconChevronDown({ className = "stroke-current", size = 10 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" fill="none" className={className}>
      <path d="M2 3.5 L5 6.5 L8 3.5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconChevronRight({ className = "stroke-current", size = 10 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" fill="none" className={className}>
      <path d="M3.5 2 L6.5 5 L3.5 8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add frontend/src/components/icons/
git commit -m "feat: add custom SVG nav icon system"
```

---

## Chunk 2: Sidebar + TopBar + Command Palette

### Task 3: Rewrite Sidebar

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Read current Sidebar.tsx in full** before editing.

- [ ] **Step 2: Rewrite Sidebar.tsx**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { useState } from "react";
import {
  IconOverview, IconChatbots, IconConversations,
  IconIntelligence, IconSettings, IconChevronDown, IconChevronRight,
} from "@/components/icons/NavIcons";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

const SETTINGS_CHILDREN = [
  { href: "/settings",               label: "General" },
  { href: "/settings/team",          label: "Team" },
  { href: "/settings/billing",       label: "Billing" },
  { href: "/settings/integrations",  label: "Integrations" },
  { href: "/settings/llm",           label: "AI Models" },
  { href: "/settings/security",      label: "Security" },
  { href: "/settings/data-retention",label: "Data Retention" },
  { href: "/settings/webhooks",      label: "Webhooks" },
];

const MAIN_NAV = [
  { href: "/dashboard",      label: "Overview",       Icon: IconOverview },
  { href: "/chatbots",       label: "Chatbots",       Icon: IconChatbots },
  { href: "/conversations",  label: "Conversations",  Icon: IconConversations },
  { href: "/intelligence",   label: "Intelligence",   Icon: IconIntelligence },
];

const PLAN_LABELS: Record<string, string> = {
  free: "Free", starter: "Starter", growth: "Growth", enterprise: "Enterprise",
};

export function Sidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const plan = workspace?.plan ?? "free";
  const isSettingsActive = pathname.startsWith("/settings");
  const [settingsOpen, setSettingsOpen] = useState(isSettingsActive);

  // Derive initials for workspace dot
  const wsInitial = workspace?.name?.[0]?.toUpperCase() ?? "W";
  const userName = user?.name ?? user?.email ?? "";
  const userInitial = userName[0]?.toUpperCase() ?? "?";

  return (
    <aside className="flex h-screen w-56 flex-col bg-white border-r border-warm-200 flex-shrink-0">
      {/* Logo + workspace switcher */}
      <div className="px-4 pt-5 pb-4 border-b border-warm-200">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-6 h-6 bg-primary-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1 7 L3 7 L5 3 L7 11 L9 5 L11 7 L13 7"
                stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="text-[17px] font-black tracking-tight text-gray-900">pulse</span>
        </div>

        {/* Workspace switcher */}
        <button className="flex items-center gap-2 w-full px-2 py-1.5 bg-warm-50 rounded-lg hover:bg-warm-100 transition-colors">
          <div className="w-5 h-5 rounded-[5px] bg-gradient-to-br from-primary-500 to-amber-400 flex items-center justify-center text-white text-[9px] font-bold flex-shrink-0">
            {wsInitial}
          </div>
          <span className="text-[11px] font-semibold text-gray-600 flex-1 text-left truncate">
            {workspace?.name ?? "Loading…"}
          </span>
          <IconChevronDown className="stroke-gray-300" />
        </button>
      </div>

      {/* Main nav */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {MAIN_NAV.map(({ href, label, Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-2.5 px-2.5 py-[7px] rounded-lg text-[12px] font-medium transition-all",
                active
                  ? "bg-primary-50 text-primary-500 font-semibold"
                  : "text-gray-500 hover:bg-warm-50 hover:text-gray-700"
              )}
            >
              <Icon
                size={16}
                className={active ? "stroke-primary-500" : "stroke-gray-400"}
              />
              {label}
              {label === "Conversations" && (
                <span className="ml-auto text-[9px] font-bold bg-primary-500 text-white px-1.5 py-0.5 rounded-full">
                  12
                </span>
              )}
            </Link>
          );
        })}

        {/* Divider */}
        <div className="h-px bg-warm-200 my-2 mx-1" />

        {/* Settings — collapsible */}
        <button
          onClick={() => setSettingsOpen((o) => !o)}
          className={clsx(
            "flex items-center gap-2.5 px-2.5 py-[7px] rounded-lg text-[12px] font-medium w-full transition-all",
            isSettingsActive
              ? "bg-primary-50 text-primary-500 font-semibold"
              : "text-gray-500 hover:bg-warm-50 hover:text-gray-700"
          )}
        >
          <IconSettings
            size={16}
            className={isSettingsActive ? "stroke-primary-500" : "stroke-gray-400"}
          />
          Settings
          <span className="ml-auto">
            {settingsOpen
              ? <IconChevronDown className={isSettingsActive ? "stroke-primary-400" : "stroke-gray-300"} />
              : <IconChevronRight className={isSettingsActive ? "stroke-primary-400" : "stroke-gray-300"} />
            }
          </span>
        </button>

        {settingsOpen && (
          <div className="pl-8 space-y-0.5">
            {SETTINGS_CHILDREN.map(({ href, label }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={clsx(
                    "block px-2 py-1.5 rounded-md text-[11px] transition-colors",
                    active
                      ? "text-primary-500 font-semibold bg-primary-50"
                      : "text-gray-400 hover:text-gray-600 hover:bg-warm-50"
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* User footer */}
      <div className="px-3 pb-4 pt-3 border-t border-warm-200">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary-500 to-amber-400 flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0">
            {userInitial}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[11px] font-semibold text-gray-700 truncate">{userName}</div>
            <div className="text-[10px] text-gray-400 truncate">{user?.email}</div>
          </div>
          <span className="text-[9px] font-bold bg-primary-50 text-primary-500 border border-primary-100 px-2 py-0.5 rounded-full flex-shrink-0">
            {PLAN_LABELS[plan]}
          </span>
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Check it renders**
```bash
cd frontend && npm run dev
# Sidebar should show warm white, orange active states, custom SVG icons, collapsed settings
```

- [ ] **Step 4: Commit**
```bash
git add frontend/src/components/layout/Sidebar.tsx frontend/src/components/icons/
git commit -m "feat: warm sidebar with custom SVG glyphs + collapsed settings"
```

---

### Task 4: Install cmdk and create Command Palette

**Files:**
- Create: `frontend/src/components/CommandPalette.tsx`
- Modify: `frontend/src/app/(dashboard)/layout.tsx`
- Modify: `frontend/src/components/layout/TopBar.tsx`

- [ ] **Step 1: Install cmdk**
```bash
cd frontend && npm install cmdk
```

- [ ] **Step 2: Create CommandPalette.tsx**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { IconSearch } from "@/components/icons/NavIcons";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

const NAV_ITEMS = [
  { label: "Overview",      href: "/dashboard",     group: "Navigate" },
  { label: "Chatbots",      href: "/chatbots",       group: "Navigate" },
  { label: "Conversations", href: "/conversations",  group: "Navigate" },
  { label: "Intelligence",  href: "/intelligence",   group: "Navigate" },
  { label: "Settings",      href: "/settings",       group: "Navigate" },
  { label: "Billing",       href: "/settings/billing", group: "Navigate" },
  { label: "Team",          href: "/settings/team",  group: "Navigate" },
];

const ACTIONS = [
  { label: "New chatbot",        action: "new-chatbot",  group: "Actions" },
  { label: "Add knowledge base", action: "new-kb",       group: "Actions" },
];

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router = useRouter();

  function handleSelect(href: string) {
    router.push(href);
    onClose();
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-black/30 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-white rounded-xl border border-warm-200 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <Command className="[&_[cmdk-input-wrapper]]:flex [&_[cmdk-input-wrapper]]:items-center [&_[cmdk-input-wrapper]]:gap-2 [&_[cmdk-input-wrapper]]:px-4 [&_[cmdk-input-wrapper]]:py-3 [&_[cmdk-input-wrapper]]:border-b [&_[cmdk-input-wrapper]]:border-warm-200">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-warm-200">
            <IconSearch className="stroke-gray-300 flex-shrink-0" size={14} />
            <Command.Input
              autoFocus
              placeholder="Search or jump to…"
              className="flex-1 text-sm text-gray-700 placeholder:text-gray-300 outline-none bg-transparent"
            />
            <kbd className="text-[10px] bg-warm-100 text-gray-400 px-1.5 py-0.5 rounded">Esc</kbd>
          </div>

          <Command.List className="max-h-72 overflow-y-auto py-2">
            <Command.Empty className="text-center text-sm text-gray-400 py-8">
              No results found.
            </Command.Empty>

            <Command.Group heading="Navigate" className="[&_[cmdk-group-heading]]:text-[9px] [&_[cmdk-group-heading]]:font-bold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-gray-400 [&_[cmdk-group-heading]]:px-4 [&_[cmdk-group-heading]]:py-2">
              {NAV_ITEMS.map((item) => (
                <Command.Item
                  key={item.href}
                  value={item.label}
                  onSelect={() => handleSelect(item.href)}
                  className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 cursor-pointer data-[selected=true]:bg-primary-50 data-[selected=true]:text-primary-500"
                >
                  {item.label}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>

          <div className="px-4 py-2 border-t border-warm-100 flex gap-3 text-[10px] text-gray-400">
            <span>↑↓ navigate</span>
            <span>↵ select</span>
            <span>Esc close</span>
          </div>
        </Command>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add global ⌘K listener in dashboard layout**

Read `frontend/src/app/(dashboard)/layout.tsx` first, then add the CommandPalette:

```tsx
// Add to frontend/src/app/(dashboard)/layout.tsx
// Add at top of file:
"use client";
import { useState, useEffect } from "react";
import { CommandPalette } from "@/components/CommandPalette";

// Inside the layout component, add:
const [cmdOpen, setCmdOpen] = useState(false);

useEffect(() => {
  function handleKey(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      setCmdOpen((o) => !o);
    }
    if (e.key === "Escape") setCmdOpen(false);
  }
  window.addEventListener("keydown", handleKey);
  return () => window.removeEventListener("keydown", handleKey);
}, []);

// In JSX, add before closing tag:
// <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />

// Export setCmdOpen via context so TopBar can trigger it too
```

- [ ] **Step 4: Rewrite TopBar.tsx**

Read current `frontend/src/components/layout/TopBar.tsx` first, then replace:

```tsx
"use client";

import { usePathname } from "next/navigation";
import { IconSearch, IconBell, IconPlus } from "@/components/icons/NavIcons";

interface TopBarProps {
  onOpenCommandPalette?: () => void;
}

// Breadcrumb map for known routes
const ROUTE_LABELS: Record<string, string> = {
  "/dashboard":     "Overview",
  "/chatbots":      "Chatbots",
  "/conversations": "Conversations",
  "/intelligence":  "Intelligence",
  "/settings":      "Settings",
};

export function TopBar({ onOpenCommandPalette }: TopBarProps) {
  const pathname = usePathname();

  // Build breadcrumb segments
  const segments = pathname.split("/").filter(Boolean);
  const pageTitle = ROUTE_LABELS["/" + segments[0]] ?? segments[0] ?? "Overview";

  return (
    <header className="h-[52px] flex items-center px-5 gap-3 bg-white border-b border-warm-200 flex-shrink-0">
      {/* Breadcrumb / title */}
      <div className="text-sm font-bold text-gray-800 tracking-tight">{pageTitle}</div>

      <div className="flex-1" />

      {/* ⌘K command bar */}
      <button
        onClick={onOpenCommandPalette}
        className="flex items-center gap-2 px-3 py-1.5 bg-warm-50 border border-warm-300 rounded-lg text-[11px] text-gray-400 hover:border-primary-300 hover:text-gray-600 transition-colors"
      >
        <IconSearch className="stroke-gray-300" size={12} />
        Search or jump to…
        <kbd className="text-[9px] bg-warm-200 text-gray-400 px-1 py-0.5 rounded ml-1">⌘K</kbd>
      </button>

      {/* Notifications */}
      <button className="w-8 h-8 flex items-center justify-center rounded-lg bg-warm-50 border border-warm-300 hover:border-primary-300 transition-colors">
        <IconBell className="stroke-gray-500" size={14} />
      </button>

      {/* Context-aware + button */}
      <button className="w-8 h-8 flex items-center justify-center rounded-lg bg-warm-50 border border-warm-300 hover:border-primary-300 transition-colors">
        <IconPlus className="stroke-gray-500" size={14} />
      </button>
    </header>
  );
}
```

- [ ] **Step 5: Wire TopBar → CommandPalette via layout context**

In the dashboard layout, pass `onOpenCommandPalette={() => setCmdOpen(true)}` to `<TopBar>`.

- [ ] **Step 6: Verify ⌘K opens the palette**
```bash
cd frontend && npm run dev
# Press ⌘K — palette should open. Type "Conv" — should filter. Press Enter — should navigate.
```

- [ ] **Step 7: Commit**
```bash
git add frontend/src/components/CommandPalette.tsx frontend/src/components/layout/TopBar.tsx frontend/src/app/(dashboard)/layout.tsx
git commit -m "feat: ⌘K command palette + warm topbar"
```

---

### Task 5: Toast system + Skeleton component

**Files:**
- Create: `frontend/src/components/ui/Toast.tsx`
- Create: `frontend/src/lib/toast.ts`
- Create: `frontend/src/components/ui/Skeleton.tsx`

- [ ] **Step 1: Install react-hot-toast**
```bash
cd frontend && npm install react-hot-toast
```

- [ ] **Step 2: Create toast wrapper**

```ts
// frontend/src/lib/toast.ts
import toast from "react-hot-toast";

export const showToast = {
  success: (msg: string) => toast.success(msg, { duration: 3000, position: "bottom-right" }),
  error:   (msg: string) => toast.error(msg,   { duration: 4000, position: "bottom-right" }),
  info:    (msg: string) => toast(msg,          { duration: 3000, position: "bottom-right" }),
};
```

- [ ] **Step 3: Add Toaster to dashboard layout**

```tsx
// In frontend/src/app/(dashboard)/layout.tsx, import and add:
import { Toaster } from "react-hot-toast";
// In JSX: <Toaster toastOptions={{ className: "text-sm font-medium" }} />
```

- [ ] **Step 4: Create Skeleton component**

```tsx
// frontend/src/components/ui/Skeleton.tsx
import { clsx } from "clsx";

interface SkeletonProps {
  className?: string;
  lines?: number;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={clsx(
        "animate-pulse bg-warm-200 rounded",
        className
      )}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-warm-200 p-4 space-y-3">
      <Skeleton className="h-7 w-20" />
      <Skeleton className="h-3 w-28" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 py-3 px-4">
      <Skeleton className="w-7 h-7 rounded-full flex-shrink-0" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-2.5 w-48" />
      </div>
      <Skeleton className="h-3 w-10" />
    </div>
  );
}
```

- [ ] **Step 5: Commit**
```bash
git add frontend/src/lib/toast.ts frontend/src/components/ui/Toast.tsx frontend/src/components/ui/Skeleton.tsx
git commit -m "feat: toast notifications + skeleton loading components"
```

---

## Chunk 3: Dashboard Redesign

### Task 6: Rewrite dashboard page

**Files:**
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx`

- [ ] **Step 1: Read current dashboard/page.tsx in full**

- [ ] **Step 2: Rewrite dashboard page**

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { getDashboard } from "@/lib/api-functions";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { BarChart, Bar, ResponsiveContainer, Tooltip } from "recharts";

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const user = useAuthStore((s) => s.user);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const firstName = user?.name?.split(" ")[0] ?? "there";

  useEffect(() => {
    if (!workspace) return;
    getDashboard(workspace.id)
      .then(setData)
      .finally(() => setLoading(false));
  }, [workspace?.id]);

  const hasData = data && data.total_conversations > 0;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Greeting */}
      <div className="mb-5">
        <h1 className="text-2xl font-black tracking-tight text-gray-900">
          {getGreeting()}, {firstName} 👋
        </h1>
        <p className="text-sm text-gray-400 mt-0.5">
          {loading
            ? "Loading your workspace…"
            : hasData
              ? `${data?.active_bots ?? 0} bot${data?.active_bots !== 1 ? "s" : ""} active · ${data?.total_conversations ?? 0} conversations this week`
              : "Your workspace is ready — create your first chatbot to get started."}
        </p>
      </div>

      {/* Quick actions */}
      <div className="flex gap-2 mb-6">
        <Link
          href="/chatbots/new"
          className="flex items-center gap-2 px-3 py-2 bg-primary-500 text-white rounded-lg text-xs font-semibold hover:bg-primary-600 transition-colors"
        >
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <path d="M5.5 1 L5.5 10 M1 5.5 L10 5.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
          New chatbot
        </Link>
        <Link
          href="/conversations"
          className="flex items-center gap-2 px-3 py-2 bg-white border border-warm-300 text-gray-600 rounded-lg text-xs font-semibold hover:border-primary-300 hover:text-primary-500 transition-colors"
        >
          View conversations
        </Link>
      </div>

      {/* Empty state — first time */}
      {!loading && !hasData && (
        <div className="bg-white rounded-xl border border-warm-200 p-10 text-center">
          <div className="w-14 h-14 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <path d="M2 14 L6 14 L9 7 L13 21 L17 10 L20 14 L26 14"
                stroke="#ff6b35" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h2 className="text-base font-bold text-gray-800 mb-2">Your first chatbot is one URL away</h2>
          <p className="text-sm text-gray-400 mb-5 max-w-xs mx-auto">
            Paste your website URL. We'll crawl it, auto-configure the bot, and give you a script tag — in under 2 minutes.
          </p>
          <div className="flex gap-2 justify-center">
            <Link href="/chatbots/new" className="px-4 py-2 bg-primary-500 text-white rounded-lg text-sm font-semibold hover:bg-primary-600 transition-colors">
              Create my first chatbot
            </Link>
            <a href="#" className="px-4 py-2 bg-white border border-warm-300 text-gray-600 rounded-lg text-sm font-semibold hover:border-primary-300 transition-colors">
              See a demo
            </a>
          </div>
        </div>
      )}

      {/* KPI grid */}
      {(loading || hasData) && (
        <>
          <div className="grid grid-cols-3 gap-3 mb-4">
            {loading ? (
              <><SkeletonCard /><SkeletonCard /><SkeletonCard /></>
            ) : (
              <>
                <div className="bg-gradient-to-br from-primary-50 to-white rounded-xl border border-primary-100 p-4">
                  <div className="text-3xl font-black tracking-tight text-primary-500">
                    {data?.resolution_rate != null ? `${(data.resolution_rate * 100).toFixed(1)}%` : "—"}
                  </div>
                  <div className="text-[11px] text-gray-400 mt-0.5">Auto-resolution rate</div>
                  {data?.resolution_rate_trend != null && (
                    <div className={`text-[11px] font-semibold mt-1 ${data.resolution_rate_trend >= 0 ? "text-green-500" : "text-red-400"}`}>
                      {data.resolution_rate_trend >= 0 ? "↑" : "↓"} {Math.abs(data.resolution_rate_trend * 100).toFixed(1)}% this week
                    </div>
                  )}
                </div>
                <div className="bg-white rounded-xl border border-warm-200 p-4">
                  <div className="text-3xl font-black tracking-tight text-gray-900">{data?.total_conversations ?? 0}</div>
                  <div className="text-[11px] text-gray-400 mt-0.5">Conversations</div>
                </div>
                <div className="bg-white rounded-xl border border-warm-200 p-4">
                  <div className="text-3xl font-black tracking-tight text-gray-900">{data?.escalated ?? 0}</div>
                  <div className="text-[11px] text-gray-400 mt-0.5">Escalated</div>
                </div>
              </>
            )}
          </div>

          {/* Trend chart */}
          {!loading && data?.trend_data?.length > 0 && (
            <div className="bg-white rounded-xl border border-warm-200 p-4">
              <div className="text-[11px] font-bold text-gray-600 mb-3">Resolution trend — 12 weeks</div>
              <ResponsiveContainer width="100%" height={60}>
                <BarChart data={data.trend_data} barSize={14}>
                  <Bar dataKey="total" fill="#ffe4d6" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="resolved" fill="#ff6b35" radius={[3, 3, 0, 0]} />
                  <Tooltip
                    contentStyle={{ fontSize: 11, border: "1px solid #f0ebe3", borderRadius: 8 }}
                    cursor={{ fill: "#faf8f5" }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify dashboard renders with greeting + skeletons → then data**
```bash
cd frontend && npm run dev
# Navigate to /dashboard — should see greeting, skeleton cards, then real data
```

- [ ] **Step 4: Commit**
```bash
git add frontend/src/app/(dashboard)/dashboard/page.tsx
git commit -m "feat: dashboard redesign — greeting, quick actions, empty state, skeleton"
```

---

## Chunk 4: Conversations Split-Pane

### Task 7: Rewrite conversations page as split-pane

**Files:**
- Modify: `frontend/src/app/(dashboard)/conversations/page.tsx`

- [ ] **Step 1: Read current conversations/page.tsx in full**

- [ ] **Step 2: Understand the API functions available**

Check `frontend/src/lib/api-functions.ts` for `getConversations`, `getConversation`, `updateConversation` signatures.

- [ ] **Step 3: Rewrite conversations page**

The key architectural change: URL param `?id=<conversationId>` controls which conversation is shown in the slide-over. No full navigation.

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getConversations, getConversation, updateConversationStatus } from "@/lib/api-functions";
import { Conversation, Message } from "@/lib/types";
import { SkeletonRow } from "@/components/ui/Skeleton";
import { showToast } from "@/lib/toast";
import { clsx } from "clsx";

const STATUS_COLOURS: Record<string, string> = {
  open:      "bg-blue-500",
  pending:   "bg-amber-400",
  resolved:  "bg-green-500",
  escalated: "bg-red-500",
  closed:    "bg-gray-300",
};

function avatarGradient(name: string) {
  const colours = [
    "from-primary-500 to-amber-400",
    "from-indigo-500 to-violet-500",
    "from-emerald-500 to-cyan-400",
    "from-pink-500 to-rose-400",
  ];
  const i = name.charCodeAt(0) % colours.length;
  return colours[i];
}

function initials(name: string) {
  return name.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}

export default function ConversationsPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(searchParams.get("id"));
  const [activeConv, setActiveConv] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("open");

  // Load list
  useEffect(() => {
    if (!workspace) return;
    setLoading(true);
    getConversations(workspace.id, { status: statusFilter === "all" ? undefined : statusFilter })
      .then(setConversations)
      .finally(() => setLoading(false));
  }, [workspace?.id, statusFilter]);

  // Load detail when activeId changes
  useEffect(() => {
    if (!workspace || !activeId) { setActiveConv(null); return; }
    setLoadingDetail(true);
    getConversation(workspace.id, activeId)
      .then(setActiveConv)
      .finally(() => setLoadingDetail(false));
  }, [workspace?.id, activeId]);

  function selectConversation(id: string) {
    setActiveId(id);
    // Update URL without navigation
    const params = new URLSearchParams(searchParams.toString());
    params.set("id", id);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  async function handleStatusChange(newStatus: string) {
    if (!workspace || !activeId) return;
    try {
      await updateConversationStatus(workspace.id, activeId, newStatus);
      setActiveConv((c: any) => c ? { ...c, status: newStatus } : c);
      setConversations((list) => list.map((c) =>
        c.id === activeId ? { ...c, status: newStatus } : c
      ));
      showToast.success(`Marked as ${newStatus}`);
    } catch {
      showToast.error("Failed to update status");
    }
  }

  const STATUS_OPTIONS = ["open", "pending", "resolved", "escalated", "closed"];

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── List panel ── */}
      <div className="w-72 flex flex-col border-r border-warm-200 bg-white flex-shrink-0">
        {/* Header */}
        <div className="px-4 py-3 border-b border-warm-100 flex items-center gap-2">
          <span className="text-sm font-bold text-gray-800 flex-1">Conversations</span>
          <span className="text-[9px] font-bold text-gray-400">{conversations.length}</span>
        </div>

        {/* Status filter chips */}
        <div className="flex gap-1.5 px-3 py-2 border-b border-warm-100 overflow-x-auto">
          {["open", "all", "escalated", "resolved"].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={clsx(
                "text-[10px] font-semibold px-2.5 py-1 rounded-full border whitespace-nowrap transition-colors",
                statusFilter === s
                  ? "bg-primary-50 border-primary-200 text-primary-500"
                  : "bg-white border-warm-300 text-gray-500 hover:border-primary-200"
              )}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {/* Rows */}
        <div className="flex-1 overflow-y-auto">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
            : conversations.map((conv) => {
                const name = conv.contact?.name ?? conv.contact?.email ?? "Unknown";
                const active = conv.id === activeId;
                return (
                  <div
                    key={conv.id}
                    onClick={() => selectConversation(conv.id)}
                    className={clsx(
                      "flex items-start gap-2.5 px-4 py-3 cursor-pointer border-b border-warm-50 transition-colors",
                      active
                        ? "bg-primary-50 border-l-2 border-l-primary-500"
                        : "hover:bg-warm-50 border-l-2 border-l-transparent"
                    )}
                  >
                    <div className={clsx(
                      "w-7 h-7 rounded-full flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0 mt-0.5 bg-gradient-to-br",
                      avatarGradient(name)
                    )}>
                      {initials(name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[11px] font-semibold text-gray-800 truncate">{name}</div>
                      <div className="text-[10px] text-gray-400 truncate mt-0.5">
                        {conv.last_message ?? "No messages"}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                      <span className="text-[9px] text-gray-400">
                        {new Date(conv.created_at).toLocaleDateString()}
                      </span>
                      <div className={clsx("w-1.5 h-1.5 rounded-full", STATUS_COLOURS[conv.status] ?? "bg-gray-300")} />
                    </div>
                  </div>
                );
              })
          }
          {!loading && conversations.length === 0 && (
            <div className="text-center py-12 text-sm text-gray-400">
              No conversations found
            </div>
          )}
        </div>
      </div>

      {/* ── Slide-over detail ── */}
      {activeConv ? (
        <div className="flex-1 flex overflow-hidden">
          {/* Messages */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Detail header */}
            <div className="flex items-center gap-3 px-5 py-3 border-b border-warm-200 bg-white flex-shrink-0">
              {(() => {
                const name = activeConv.contact?.name ?? activeConv.contact?.email ?? "Unknown";
                return (
                  <>
                    <div className={clsx(
                      "w-8 h-8 rounded-full flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0 bg-gradient-to-br",
                      avatarGradient(name)
                    )}>
                      {initials(name)}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-gray-800">{name}</div>
                      <div className="text-[10px] text-gray-400">
                        {activeConv.chatbot?.name} · {new Date(activeConv.created_at).toLocaleString()}
                      </div>
                    </div>
                  </>
                );
              })()}
              <div className="ml-auto flex items-center gap-2">
                <select
                  value={activeConv.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  className="text-[10px] font-bold px-3 py-1.5 rounded-full bg-green-50 text-green-600 border border-green-200 cursor-pointer outline-none"
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Messages area */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-warm-50">
              {(activeConv.messages ?? []).map((msg: Message) => (
                <div
                  key={msg.id}
                  className={clsx("flex flex-col max-w-[72%]", msg.author_type === "user" ? "self-end items-end ml-auto" : "self-start items-start")}
                >
                  <span className="text-[9px] text-gray-400 mb-1">
                    {msg.author_type === "user" ? "User" : "Bot"} · {new Date(msg.created_at).toLocaleTimeString()}
                  </span>
                  <div className={clsx(
                    "px-3 py-2 rounded-xl text-[11px] leading-relaxed",
                    msg.author_type === "user"
                      ? "bg-primary-500 text-white rounded-tr-sm"
                      : "bg-white border border-warm-200 text-gray-700 rounded-tl-sm"
                  )}>
                    {msg.content}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Metadata sidebar */}
          <div className="w-48 border-l border-warm-200 bg-white flex-shrink-0 p-4 overflow-y-auto">
            <div className="space-y-4">
              <div>
                <div className="text-[9px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Contact</div>
                <div className="text-[11px] font-semibold text-gray-700">{activeConv.contact?.name ?? "—"}</div>
                <div className="text-[10px] text-gray-400">{activeConv.contact?.email ?? "—"}</div>
              </div>
              {activeConv.confidence_score != null && (
                <div>
                  <div className="text-[9px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Confidence</div>
                  <div className="h-1.5 bg-warm-200 rounded-full">
                    <div
                      className="h-1.5 bg-green-500 rounded-full"
                      style={{ width: `${(activeConv.confidence_score * 100).toFixed(0)}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-green-600 font-semibold mt-1">
                    {(activeConv.confidence_score * 100).toFixed(0)}%
                  </div>
                </div>
              )}
              <div>
                <div className="text-[9px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Bot</div>
                <div className="text-[11px] text-gray-600">{activeConv.chatbot?.name ?? "—"}</div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center bg-warm-50 text-sm text-gray-400">
          Select a conversation to view details
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Check types — ensure `getConversation`, `updateConversationStatus` exist in api-functions.ts**

If `updateConversationStatus` doesn't exist, add it:
```ts
// In frontend/src/lib/api-functions.ts
export async function updateConversationStatus(
  workspaceId: string,
  conversationId: string,
  status: string
) {
  return apiClient.patch(
    `/workspaces/${workspaceId}/conversations/${conversationId}`,
    { status }
  );
}
```

- [ ] **Step 5: Verify split-pane works**
```bash
# Navigate to /conversations
# Should see list on left, click a row → detail appears on right
# Status dropdown in header → updates optimistically, shows toast
```

- [ ] **Step 6: Commit**
```bash
git add frontend/src/app/(dashboard)/conversations/ frontend/src/lib/api-functions.ts
git commit -m "feat: conversations split-pane with URL param + inline status"
```

---

## Chunk 5: Chatbot Detail — Tabs + Sources + Customize

### Task 8: Reorder chatbot tabs

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx`

- [ ] **Step 1: Read current chatbot [id] layout.tsx in full**

- [ ] **Step 2: Replace tab definitions**

Find the tab array in the layout and replace with the new order + icons:

```tsx
// Replace the tabs array in frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx
import {
  IconKnowledge, IconConfigure, IconActions,
  IconAppearance, IconTest, IconPublish
} from "@/components/icons/NavIcons";

const tabs = [
  { href: "sources",   label: "Knowledge",   Icon: IconKnowledge  },
  { href: "settings",  label: "Configure",   Icon: IconConfigure  },
  { href: "actions",   label: "Actions",     Icon: IconActions    },
  { href: "customize", label: "Appearance",  Icon: IconAppearance },
  { href: "chat",      label: "Test",        Icon: IconTest       },
  { href: "deploy",    label: "Publish",     Icon: IconPublish    },
];
```

Update each tab link to render `<Icon size={12} />` next to the label:
```tsx
<Link href={`/chatbots/${chatbotId}/${tab.href}`} className={clsx(
  "flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap",
  isActive
    ? "border-primary-500 text-primary-500"
    : "border-transparent text-gray-400 hover:text-gray-600"
)}>
  <tab.Icon className={isActive ? "stroke-primary-500" : "stroke-current"} />
  {tab.label}
</Link>
```

- [ ] **Step 3: Verify tab order renders correctly**
```bash
# Navigate to /chatbots/<id>
# Tabs should be: Knowledge → Configure → Actions → Appearance → Test → Publish
```

- [ ] **Step 4: Commit**
```bash
git add frontend/src/app/(dashboard)/chatbots/\[id\]/layout.tsx
git commit -m "feat: chatbot tabs reordered — Knowledge → Configure → Actions → Appearance → Test → Publish"
```

---

### Task 9: Improve Sources table

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/sources/SourcesTab.tsx`

- [ ] **Step 1: Read current SourcesTab.tsx in full**

- [ ] **Step 2: Apply targeted changes**

**Change 1 — Remove "Chunks" column, add "Last synced":**
```tsx
// Replace th/td for chunks with:
<th className="...">Last synced</th>
// In td:
<td>{doc.last_synced_at ? new Date(doc.last_synced_at).toLocaleDateString() : "—"}</td>
```

**Change 2 — Row hover actions (opacity transition):**
```tsx
// Wrap action buttons in:
<div className="flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
  <button onClick={() => handleReindex(doc.id)} className="text-[9px] px-2 py-1 rounded-md border border-warm-300 text-gray-500 hover:border-primary-300 hover:text-primary-500 bg-white">
    Reindex
  </button>
  <button onClick={() => handleDelete(doc.id)} className="text-[9px] px-2 py-1 rounded-md border border-red-100 text-red-400 hover:border-red-300 bg-white">
    ×
  </button>
</div>
// Add group class to <tr>: className="group ..."
```

**Change 3 — Failed status pill with inline Retry:**
```tsx
// In status pill rendering, for failed docs:
{doc.status === "failed" ? (
  <span className="inline-flex items-center gap-1.5 text-[9px] font-bold px-2 py-1 bg-red-50 text-red-500 rounded-full border border-red-100">
    ● Failed
    <button
      onClick={() => handleReindex(doc.id)}
      className="underline hover:no-underline"
    >
      Retry
    </button>
  </span>
) : /* existing pill */ null}
```

**Change 4 — Show toast on reindex/delete:**
```tsx
import { showToast } from "@/lib/toast";
// In handleReindex: showToast.info("Reindexing started…")
// In handleDelete: showToast.success("Document removed")
```

- [ ] **Step 3: Commit**
```bash
git add frontend/src/app/(dashboard)/chatbots/\[id\]/sources/
git commit -m "feat: sources table — hover actions, retry-on-fail, remove chunks col, toasts"
```

---

### Task 10: Sectioned widget customize form

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx`

- [ ] **Step 1: Read current customize/page.tsx in full**

- [ ] **Step 2: Add sticky save bar at top**

Wrap the existing form in a relative container. Add a sticky bar:
```tsx
<div className="sticky top-0 z-10 bg-white border-b border-warm-200 px-6 py-3 flex items-center justify-between">
  <span className="text-sm font-bold text-gray-800">Appearance</span>
  <div className="flex gap-2">
    <button onClick={handleReset} className="px-3 py-1.5 text-xs font-semibold text-gray-500 border border-warm-300 rounded-lg hover:border-primary-300 transition-colors">
      Reset defaults
    </button>
    <button onClick={handleSave} disabled={saving} className="px-3 py-1.5 text-xs font-semibold bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors disabled:opacity-50">
      {saving ? "Saving…" : "Save changes"}
    </button>
  </div>
</div>
```

**Add section dividers** between logical groups. Wrap each group:
```tsx
<div className="mb-6">
  <h3 className="text-[9px] font-bold uppercase tracking-wider text-primary-500 border-b border-primary-50 pb-2 mb-4">
    Identity
  </h3>
  {/* bot name, brand colour, welcome message fields */}
</div>

<div className="mb-6">
  <h3 className="text-[9px] font-bold uppercase tracking-wider text-primary-500 border-b border-primary-50 pb-2 mb-4">
    Layout & Position
  </h3>
  {/* position toggle */}
</div>

<div className="mb-6">
  <h3 className="text-[9px] font-bold uppercase tracking-wider text-primary-500 border-b border-primary-50 pb-2 mb-4">
    Behaviour
  </h3>
  {/* lead capture, GDPR, persist toggles */}
</div>

<details className="mb-6">
  <summary className="text-[9px] font-bold uppercase tracking-wider text-gray-400 cursor-pointer mb-2">
    Advanced (custom CSS)
  </summary>
  {/* custom CSS textarea */}
</details>
```

**Add desktop/mobile preview toggle:**
```tsx
const [previewMode, setPreviewMode] = useState<"desktop" | "mobile">("desktop");

// In preview panel:
<div className="flex gap-1.5 mb-3">
  {(["desktop", "mobile"] as const).map((m) => (
    <button
      key={m}
      onClick={() => setPreviewMode(m)}
      className={clsx(
        "flex-1 text-[10px] font-semibold py-1.5 rounded-lg border transition-colors",
        previewMode === m
          ? "bg-primary-50 border-primary-200 text-primary-500"
          : "bg-white border-warm-300 text-gray-400"
      )}
    >
      {m.charAt(0).toUpperCase() + m.slice(1)}
    </button>
  ))}
</div>
// When previewMode === "mobile", wrap preview in a narrower container (320px → 200px)
```

- [ ] **Step 3: Show success toast on save**
```tsx
// In handleSave success:
showToast.success("Widget settings saved");
```

- [ ] **Step 4: Commit**
```bash
git add frontend/src/app/(dashboard)/chatbots/\[id\]/customize/
git commit -m "feat: widget customize — sectioned form, sticky save, mobile preview toggle, toast"
```

---

## Chunk 6: Empty States + Micro-interactions

### Task 11: Copy button micro-interaction

**Files:**
- Create: `frontend/src/components/ui/CopyButton.tsx`

- [ ] **Step 1: Create CopyButton component**

```tsx
"use client";

import { useState } from "react";
import { clsx } from "clsx";

interface CopyButtonProps {
  text: string;
  className?: string;
  label?: string;
}

export function CopyButton({ text, className, label = "Copy" }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      onClick={handleCopy}
      className={clsx(
        "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition-all",
        copied
          ? "bg-green-50 border-green-200 text-green-600"
          : "bg-white border-warm-300 text-gray-600 hover:border-primary-300 hover:text-primary-500",
        className
      )}
    >
      {copied ? (
        <>
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <path d="M2 5.5 L4.5 8 L9 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <rect x="1" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
            <path d="M3.5 3 L3.5 1.5 Q3.5 1 4 1 L9.5 1 Q10 1 10 1.5 L10 7 Q10 7.5 9.5 7.5 L8 7.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          {label}
        </>
      )}
    </button>
  );
}
```

- [ ] **Step 2: Replace all copy buttons in the codebase with CopyButton**

Find existing copy buttons (search for `navigator.clipboard` or `copy` button patterns in:
- `frontend/src/app/(dashboard)/chatbots/[id]/deploy/page.tsx`
- `frontend/src/app/(dashboard)/onboarding/page.tsx`
- Any embed code display components

Replace with `<CopyButton text={embedCode} />`.

- [ ] **Step 3: Commit**
```bash
git add frontend/src/components/ui/CopyButton.tsx
git commit -m "feat: CopyButton with Copied! feedback animation"
```

---

### Task 12: Breadcrumbs on sub-pages

**Files:**
- Create: `frontend/src/components/ui/Breadcrumb.tsx`

- [ ] **Step 1: Create Breadcrumb component**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ROUTE_MAP: Record<string, { label: string; href: string }> = {
  "chatbots":      { label: "Chatbots",      href: "/chatbots" },
  "conversations": { label: "Conversations", href: "/conversations" },
  "settings":      { label: "Settings",      href: "/settings" },
  "intelligence":  { label: "Intelligence",  href: "/intelligence" },
};

interface BreadcrumbProps {
  /** Override the leaf (last) label — e.g. chatbot name */
  leafLabel?: string;
}

export function Breadcrumb({ leafLabel }: BreadcrumbProps) {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  // Only show breadcrumb when ≥2 segments deep
  if (segments.length < 2) return null;

  const parent = ROUTE_MAP[segments[0]];
  if (!parent) return null;

  return (
    <nav className="flex items-center gap-1.5 text-xs text-gray-400 mb-4">
      <Link href={parent.href} className="hover:text-primary-500 transition-colors font-medium">
        {parent.label}
      </Link>
      <span className="text-gray-300">›</span>
      <span className="text-gray-600 font-semibold truncate max-w-[200px]">
        {leafLabel ?? segments[segments.length - 1]}
      </span>
    </nav>
  );
}
```

- [ ] **Step 2: Add Breadcrumb to chatbot detail page**

In `frontend/src/app/(dashboard)/chatbots/[id]/page.tsx` and `layout.tsx`, add:
```tsx
import { Breadcrumb } from "@/components/ui/Breadcrumb";
// Near top of page content:
<Breadcrumb leafLabel={chatbot?.name} />
```

- [ ] **Step 3: Commit**
```bash
git add frontend/src/components/ui/Breadcrumb.tsx
git commit -m "feat: breadcrumb navigation on chatbot sub-pages"
```

---

### Task 13: Page title updates

**Files:**
- Modify: `frontend/src/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Add dynamic page title via useEffect in layout, OR use Next.js metadata**

The cleanest approach in Next.js App Router is to add a `title` template in the root layout and export `metadata` from each page. Add to root layout:

```tsx
// frontend/src/app/layout.tsx
export const metadata = {
  title: { template: "%s — PulseLite", default: "PulseLite" },
  description: "AI-powered website chatbot",
};
```

Then add to key pages:
```tsx
// frontend/src/app/(dashboard)/dashboard/page.tsx
export const metadata = { title: "Overview" };

// frontend/src/app/(dashboard)/conversations/page.tsx
export const metadata = { title: "Conversations" };

// frontend/src/app/(dashboard)/chatbots/page.tsx
export const metadata = { title: "Chatbots" };
```

Note: `metadata` export cannot coexist with `"use client"` directive. For client pages, use `useEffect(() => { document.title = "Conversations — PulseLite"; }, [])` at the top.

- [ ] **Step 2: Add titles to all dashboard pages**

For each `page.tsx` in `(dashboard)/`:
- `dashboard/page.tsx` → "Overview — PulseLite"
- `conversations/page.tsx` → "Conversations — PulseLite"
- `chatbots/page.tsx` → "Chatbots — PulseLite"
- `chatbots/[id]/page.tsx` → `${chatbot.name} — PulseLite` (set dynamically in useEffect)
- `settings/page.tsx` → "Settings — PulseLite"

- [ ] **Step 3: Commit**
```bash
git add frontend/src/app/layout.tsx frontend/src/app/(dashboard)/
git commit -m "feat: dynamic page titles on all dashboard routes"
```

---

### Task 14: Keyboard shortcuts

**Files:**
- Create: `frontend/src/hooks/useKeyboardShortcuts.ts`
- Modify: `frontend/src/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Create keyboard shortcut hook**

```ts
// frontend/src/hooks/useKeyboardShortcuts.ts
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function useKeyboardShortcuts(onOpenCommandPalette: () => void) {
  const router = useRouter();

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      // Skip if user is typing in an input/textarea
      const tag = (e.target as HTMLElement).tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return;

      switch (e.key) {
        case "g":
          // g then d = go to dashboard (simple single-key for now)
          router.push("/dashboard");
          break;
        case "c":
          router.push("/conversations");
          break;
        case "b":
          router.push("/chatbots");
          break;
        case "/":
          e.preventDefault();
          onOpenCommandPalette();
          break;
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [router, onOpenCommandPalette]);
}
```

- [ ] **Step 2: Wire into dashboard layout**

```tsx
// In frontend/src/app/(dashboard)/layout.tsx:
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
// Inside component:
useKeyboardShortcuts(() => setCmdOpen(true));
```

- [ ] **Step 3: Commit**
```bash
git add frontend/src/hooks/useKeyboardShortcuts.ts frontend/src/app/(dashboard)/layout.tsx
git commit -m "feat: keyboard shortcuts — c=conversations, b=chatbots, /=command palette"
```

---

## Final Step: Run full test suite

- [ ] **Step 1: Run frontend tests**
```bash
cd frontend && npm run test
```

- [ ] **Step 2: Run E2E smoke test**
```bash
make test-e2e
# Verify login, chatbot creation, conversations still work
```

- [ ] **Step 3: Visual check — walk through all 8 areas**

Checklist:
- [ ] Sidebar: warm white, 5 top-level items, custom SVG glyphs, settings collapses/expands, workspace switcher visible
- [ ] TopBar: ⌘K bar triggers command palette, ⌘K keyboard shortcut works
- [ ] Dashboard: greeting, quick actions, skeleton → data, empty state for new workspace
- [ ] Conversations: split-pane, clicking row shows detail, status dropdown updates inline with toast
- [ ] Chatbot tabs: correct order Knowledge → Configure → Actions → Appearance → Test → Publish
- [ ] Sources table: hover shows actions, failed pill shows Retry link, no Chunks column
- [ ] Widget customize: sections visible, sticky save bar, mobile/desktop toggle
- [ ] Copy buttons: show "Copied!" for 1.5s then revert

- [ ] **Step 4: Final commit**
```bash
git add -A
git commit -m "feat: UX redesign complete — warm studio, custom icons, split-pane conversations, ⌘K, micro-interactions"
```
