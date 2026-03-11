# Next.js → Vite + React Router Migration Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Next.js App Router with Vite + React Router, keeping all components, stores, and API layer unchanged.

**Architecture:** Pure SPA — Vite serves a single `index.html`; React Router handles all client-side routing; layouts become route wrapper components using `<Outlet />`; no SSR. The `src/app/` directory is kept as-is (files are just React components — no Next.js conventions required).

**Tech Stack:** Vite 6, React Router v7 (`react-router-dom`), React 19, TypeScript 5, Tailwind CSS 3, Zustand 5, Vitest 2 (already Vite-based — minimal change).

---

## File Structure

**New files to create:**
- `frontend/vite.config.ts` — Vite dev server + build config
- `frontend/index.html` — SPA entry HTML with Google Fonts link
- `frontend/src/main.tsx` — React DOM entry point
- `frontend/src/App.tsx` — BrowserRouter + full route tree

**Files to modify:**
- `frontend/package.json` — swap `next` → `react-router-dom`, update scripts
- `frontend/tsconfig.json` — remove Next.js plugin, fix jsx mode
- `frontend/tailwind.config.ts` — update content paths
- `frontend/docker-compose.yml` (line 96) — `NEXT_PUBLIC_API_URL` → `VITE_API_URL`
- `frontend/src/app/(dashboard)/layout.tsx` — `{children}` → `<Outlet />`
- `frontend/src/app/(auth)/layout.tsx` — `{children}` → `<Outlet />`
- `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx` — `{children}` → `<Outlet />`, all next/* imports
- `frontend/src/components/auth/ProtectedRoute.tsx` — next/navigation → react-router-dom
- `frontend/src/components/layout/Sidebar.tsx` — next/link + next/navigation → react-router-dom
- `frontend/src/components/layout/TopBar.tsx` — next/navigation → react-router-dom
- `frontend/src/components/ui/Breadcrumb.tsx` — next/link + next/navigation → react-router-dom
- `frontend/src/components/chatbots/ChatbotTabNav.tsx` — next/link + next/navigation → react-router-dom
- `frontend/src/components/CommandPalette.tsx` — next/navigation → react-router-dom
- `frontend/src/hooks/useAuth.ts` — next/navigation → react-router-dom
- `frontend/src/hooks/useKeyboardShortcuts.ts` — next/navigation → react-router-dom
- `frontend/src/components/copilot/CopilotChat.tsx` — next/navigation → react-router-dom
- All 27 page files — remove `"use client"`, swap next/* imports
- 10 files using `process.env.NEXT_PUBLIC_*` — swap to `import.meta.env.VITE_*`

**Files to delete:**
- `frontend/next.config.mjs`
- `frontend/next-env.d.ts`
- `frontend/src/app/(dashboard)/page.tsx` (redirect handled in App.tsx)
- `frontend/src/app/layout.tsx` (replaced by index.html + main.tsx)

---

## Import Replacement Reference

Every subagent doing import swaps MUST follow this table exactly:

| Next.js | React Router / Vite |
|---------|---------------------|
| `import { useRouter } from 'next/navigation'` | `import { useNavigate } from 'react-router-dom'` |
| `import { useParams } from 'next/navigation'` | `import { useParams } from 'react-router-dom'` |
| `import { usePathname } from 'next/navigation'` | `import { useLocation } from 'react-router-dom'` |
| `import { useSearchParams } from 'next/navigation'` | `import { useSearchParams } from 'react-router-dom'` |
| `import { redirect } from 'next/navigation'` | `import { Navigate } from 'react-router-dom'` |
| `import Link from 'next/link'` | `import { Link } from 'react-router-dom'` |
| `const router = useRouter()` | `const navigate = useNavigate()` |
| `router.push(path)` | `navigate(path)` |
| `router.replace(path)` | `navigate(path, { replace: true })` |
| `router.back()` | `navigate(-1)` |
| `const pathname = usePathname()` | `const { pathname } = useLocation()` |
| `const searchParams = useSearchParams()` | `const [searchParams] = useSearchParams()` |
| `<Link href="...">` | `<Link to="...">` |
| `"use client"` directive | DELETE — no equivalent needed |
| `process.env.NEXT_PUBLIC_API_URL` | `import.meta.env.VITE_API_URL` |
| `process.env.NEXT_PUBLIC_APP_URL` | `import.meta.env.VITE_APP_URL` |

---

## Chunk 1: Build Infrastructure

### Task 1: Vite scaffold (vite.config.ts, index.html, package.json, tsconfig.json)

**Files:**
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Modify: `frontend/package.json`
- Modify: `frontend/tsconfig.json`
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
  envPrefix: 'VITE_',
})
```

- [ ] **Step 2: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Pulse</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="" />
    <link
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
      rel="stylesheet"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Update `frontend/package.json`**

Change `"dependencies"`:
- Remove: `"next": "15.3.9"`
- Add: `"react-router-dom": "^7.0.0"`

Change `"devDependencies"`:
- Remove: `"eslint-config-next": "15.3.9"`
- Add: `"vite": "^6.0.0"` (currently only `@vitejs/plugin-react` is present, `vite` itself is missing)

Change `"scripts"` to:
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "lint": "eslint src",
  "test": "vitest run",
  "test:watch": "vitest",
  "test:coverage": "vitest run --coverage",
  "test:e2e": "playwright test",
  "test:e2e:headed": "playwright test --headed",
  "test:e2e:report": "playwright show-report"
}
```

- [ ] **Step 4: Update `frontend/tsconfig.json`**

Replace entire file contents with:
```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "paths": {
      "@/*": ["./src/*"]
    },
    "target": "ES2017"
  },
  "include": ["src", "vite.config.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 5: Update `frontend/tailwind.config.ts` content paths**

Change the `content` array to:
```typescript
content: [
  "./index.html",
  "./src/**/*.{js,ts,jsx,tsx}",
],
```

- [ ] **Step 6: Commit**

```bash
git add frontend/vite.config.ts frontend/index.html frontend/package.json frontend/tsconfig.json frontend/tailwind.config.ts
git commit -m "chore: add Vite scaffold (vite.config, index.html, update tsconfig + package.json)"
```

---

### Task 2: App entry point and route tree

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Modify: `frontend/src/app/(dashboard)/layout.tsx`
- Modify: `frontend/src/app/(auth)/layout.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx`
- Delete: `frontend/src/app/layout.tsx`
- Delete: `frontend/src/app/(dashboard)/page.tsx`

- [ ] **Step 1: Create `frontend/src/main.tsx`**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './app/globals.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

- [ ] **Step 2: Create `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

// Layouts
import DashboardLayout from './app/(dashboard)/layout'
import AuthLayout from './app/(auth)/layout'

// Auth pages
import LoginPage from './app/(auth)/login/page'
import RegisterPage from './app/(auth)/register/page'
import AcceptInvitePage from './app/(auth)/accept-invite/page'

// Dashboard pages
import DashboardPage from './app/(dashboard)/dashboard/page'
import OnboardingPage from './app/(dashboard)/onboarding/page'
import WorkspacesPage from './app/(dashboard)/workspaces/page'

// Chatbot pages
import ChatbotsPage from './app/(dashboard)/chatbots/page'
import NewChatbotPage from './app/(dashboard)/chatbots/new/page'
import ChatbotLayout from './app/(dashboard)/chatbots/[id]/layout'
import KnowledgePage from './app/(dashboard)/chatbots/[id]/page'
import ChatbotSettingsPage from './app/(dashboard)/chatbots/[id]/settings/page'
import ActionsPage from './app/(dashboard)/chatbots/[id]/actions/page'
import CustomizePage from './app/(dashboard)/chatbots/[id]/customize/page'
import ChatPage from './app/(dashboard)/chatbots/[id]/chat/page'
import DeployPage from './app/(dashboard)/chatbots/[id]/deploy/page'
import ArticlesPage from './app/(dashboard)/chatbots/[id]/articles/page'
import SourcesPage from './app/(dashboard)/chatbots/[id]/sources/page'

// Conversation pages
import ConversationsPage from './app/(dashboard)/conversations/page'
import ConversationDetailPage from './app/(dashboard)/conversations/[id]/page'

// Intelligence pages
import IntelligencePage from './app/(dashboard)/intelligence/page'
import SentimentPage from './app/(dashboard)/intelligence/sentiment/page'
import GapsPage from './app/(dashboard)/intelligence/gaps/page'
import GapDetailPage from './app/(dashboard)/intelligence/gaps/[id]/page'

// Article pages
import ArticleDetailPage from './app/(dashboard)/articles/[id]/page'

// Settings pages
import SettingsPage from './app/(dashboard)/settings/page'
import BillingPage from './app/(dashboard)/settings/billing/page'
import DataRetentionPage from './app/(dashboard)/settings/data-retention/page'
import IntegrationsPage from './app/(dashboard)/settings/integrations/page'
import LLMPage from './app/(dashboard)/settings/llm/page'
import SecurityPage from './app/(dashboard)/settings/security/page'
import TeamPage from './app/(dashboard)/settings/team/page'
import WebhooksPage from './app/(dashboard)/settings/webhooks/page'

// Public
import PublicChatPage from './app/chat/[chatbotId]/page'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* Auth */}
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/accept-invite" element={<AcceptInvitePage />} />
        </Route>

        {/* Dashboard */}
        <Route element={<DashboardLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/workspaces" element={<WorkspacesPage />} />

          <Route path="/chatbots" element={<ChatbotsPage />} />
          <Route path="/chatbots/new" element={<NewChatbotPage />} />
          <Route path="/chatbots/:id" element={<ChatbotLayout />}>
            <Route index element={<KnowledgePage />} />
            <Route path="settings" element={<ChatbotSettingsPage />} />
            <Route path="actions" element={<ActionsPage />} />
            <Route path="customize" element={<CustomizePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="deploy" element={<DeployPage />} />
            <Route path="articles" element={<ArticlesPage />} />
            <Route path="sources" element={<SourcesPage />} />
          </Route>

          <Route path="/conversations" element={<ConversationsPage />} />
          <Route path="/conversations/:id" element={<ConversationDetailPage />} />

          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/intelligence/sentiment" element={<SentimentPage />} />
          <Route path="/intelligence/gaps" element={<GapsPage />} />
          <Route path="/intelligence/gaps/:id" element={<GapDetailPage />} />

          <Route path="/articles/:id" element={<ArticleDetailPage />} />

          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/settings/billing" element={<BillingPage />} />
          <Route path="/settings/data-retention" element={<DataRetentionPage />} />
          <Route path="/settings/integrations" element={<IntegrationsPage />} />
          <Route path="/settings/llm" element={<LLMPage />} />
          <Route path="/settings/security" element={<SecurityPage />} />
          <Route path="/settings/team" element={<TeamPage />} />
          <Route path="/settings/webhooks" element={<WebhooksPage />} />
        </Route>

        {/* Public chat widget */}
        <Route path="/chat/:chatbotId" element={<PublicChatPage />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 3: Update `frontend/src/app/(dashboard)/layout.tsx`**

Replace entire file with (key change: remove `children` prop, import and use `<Outlet />`):

```tsx
"use client"; // DELETE this line entirely

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
  return (
    <ProtectedRoute>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar />
          <div className="flex flex-1 overflow-hidden">
            <main className="flex-1 overflow-auto bg-[#faf8f5] p-6">
              <Outlet />
            </main>
            <CopilotPanel />
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

- [ ] **Step 4: Update `frontend/src/app/(auth)/layout.tsx`**

Replace entire file with:

```tsx
import { Outlet } from 'react-router-dom'

export default function AuthLayout() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary-50 via-white to-primary-100">
      <div className="w-full max-w-md px-4">
        <Outlet />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Update `frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx`**

This is the most complex layout. Replace all Next.js imports and `{children}` with React Router equivalents:

```tsx
// Remove "use client" entirely
import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation, Link, Outlet } from "react-router-dom";
import { clsx } from "clsx";
import { Copy, Pencil, Check, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { Chatbot } from "@/lib/types";
import { getChatbot, duplicateChatbot, updateChatbot } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useChatbotStore } from "@/stores/chatbot-store";
import { useCopilot } from "@/components/copilot/CopilotProvider";
import {
  IconKnowledge,
  IconConfigure,
  IconActions,
  IconAppearance,
  IconTest,
  IconPublish,
} from "@/components/icons/NavIcons";

const TABS = [
  { label: "Knowledge",  segment: null,        Icon: IconKnowledge },
  { label: "Configure",  segment: "settings",  Icon: IconConfigure },
  { label: "Actions",    segment: "actions",   Icon: IconActions },
  { label: "Appearance", segment: "customize", Icon: IconAppearance },
  { label: "Test",       segment: "chat",      Icon: IconTest },
  { label: "Publish",    segment: "deploy",    Icon: IconPublish },
] as const;

export default function ChatbotLayout() {
  const { id: chatbotId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const { currentChatbot: chatbot, setChatbot, patchChatbot, clearChatbot } = useChatbotStore();
  const { register } = useCopilot();
  const [loading, setLoading] = useState(true);
  const [duplicating, setDuplicating] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [savingName, setSavingName] = useState(false);

  useEffect(() => {
    if (!workspace || !chatbotId) return;
    getChatbot(workspace.id, chatbotId)
      .then((bot) => {
        setChatbot(bot);
        register({
          page: "chatbot-settings",
          chatbot_id: bot.id,
          data: {
            chatbot: {
              name: bot.name,
              display_name: bot.display_name,
              llm_model: bot.llm_model,
              confidence_threshold: bot.confidence_threshold,
              is_active: bot.is_active,
              tone: bot.tone,
            },
          },
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => clearChatbot();
  }, [workspace, chatbotId, register]);

  function startEditName() {
    setNameValue(chatbot?.display_name || chatbot?.name || "");
    setEditingName(true);
  }

  async function saveName() {
    if (!workspace || !chatbot || !nameValue.trim()) return;
    setSavingName(true);
    try {
      const updated = await updateChatbot(workspace.id, chatbot.id, { display_name: nameValue.trim() });
      patchChatbot({ display_name: updated.display_name });
      setEditingName(false);
    } catch {
    } finally {
      setSavingName(false);
    }
  }

  async function handleDuplicate() {
    if (!workspace || !chatbot) return;
    setDuplicating(true);
    try {
      const copy = await duplicateChatbot(workspace.id, chatbot.id);
      navigate(`/chatbots/${copy.id}`);
    } catch {
    } finally {
      setDuplicating(false);
    }
  }

  function tabHref(segment: string | null): string {
    return segment ? `/chatbots/${chatbotId}/${segment}` : `/chatbots/${chatbotId}`;
  }

  function isActive(segment: string | null): boolean {
    if (segment === null) {
      return pathname === `/chatbots/${chatbotId}`;
    }
    return pathname.startsWith(`/chatbots/${chatbotId}/${segment}`);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <div>
      <Link
        to="/chatbots"
        className="inline-flex items-center gap-1 mb-3 text-sm text-gray-500 hover:text-gray-700 transition-colors"
      >
        ← Chatbots
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          {editingName ? (
            <div className="flex items-center gap-2">
              <input
                autoFocus
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveName();
                  if (e.key === "Escape") setEditingName(false);
                }}
                className="text-2xl font-bold text-gray-900 border-b-2 border-primary-500 bg-transparent focus:outline-none w-64"
              />
              <button onClick={saveName} disabled={savingName} className="text-green-600 hover:text-green-700 disabled:opacity-50">
                <Check className="h-5 w-5" />
              </button>
              <button onClick={() => setEditingName(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 group">
              <h1 className="text-2xl font-bold text-gray-900">
                {chatbot?.display_name || chatbot?.name}
              </h1>
              <button
                onClick={startEditName}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-gray-600"
              >
                <Pencil className="h-4 w-4" />
              </button>
            </div>
          )}
          <p className="text-sm text-gray-500 mt-1">
            {chatbot?.llm_model?.split("/").pop()} / {chatbot?.tone}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleDuplicate}
          loading={duplicating}
        >
          <Copy className="h-4 w-4 mr-1.5" />
          Duplicate
        </Button>
      </div>

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {TABS.map((tab) => {
            const { Icon } = tab;
            return (
              <Link
                key={tab.label}
                to={tabHref(tab.segment)}
                className={clsx(
                  "pb-3 text-sm font-medium border-b-2 transition-all duration-200 flex items-center gap-1.5",
                  isActive(tab.segment)
                    ? "border-primary-500 text-primary-500"
                    : "border-transparent text-gray-400 hover:text-gray-600 hover:border-gray-300",
                )}
              >
                <Icon size={12} />
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <Outlet />
    </div>
  );
}
```

- [ ] **Step 6: Delete obsolete Next.js-only files**

```bash
rm frontend/src/app/layout.tsx
rm frontend/src/app/(dashboard)/page.tsx
rm frontend/next.config.mjs
rm frontend/next-env.d.ts 2>/dev/null || true
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/main.tsx frontend/src/App.tsx \
  "frontend/src/app/(dashboard)/layout.tsx" \
  "frontend/src/app/(auth)/layout.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/layout.tsx"
git rm frontend/src/app/layout.tsx "frontend/src/app/(dashboard)/page.tsx" \
  frontend/next.config.mjs frontend/next-env.d.ts 2>/dev/null || true
git commit -m "feat: add Vite entry point, route tree, and update layout components to use Outlet"
```

---

## Chunk 2: Shared Components

### Task 3: Navigation imports in shared components and hooks

Update all files that import from `next/navigation` or `next/link` outside of page files. Remove all `"use client"` directives.

**Files:**
- Modify: `frontend/src/components/auth/ProtectedRoute.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/components/layout/TopBar.tsx`
- Modify: `frontend/src/components/ui/Breadcrumb.tsx`
- Modify: `frontend/src/components/chatbots/ChatbotTabNav.tsx`
- Modify: `frontend/src/components/CommandPalette.tsx`
- Modify: `frontend/src/components/copilot/CopilotChat.tsx`
- Modify: `frontend/src/hooks/useAuth.ts`
- Modify: `frontend/src/hooks/useKeyboardShortcuts.ts`

- [ ] **Step 1: Read all 9 files before editing**

```bash
cat frontend/src/components/auth/ProtectedRoute.tsx
cat frontend/src/components/layout/TopBar.tsx
cat frontend/src/components/ui/Breadcrumb.tsx
cat frontend/src/components/chatbots/ChatbotTabNav.tsx
cat frontend/src/components/CommandPalette.tsx
cat frontend/src/components/copilot/CopilotChat.tsx
cat frontend/src/hooks/useAuth.ts
cat frontend/src/hooks/useKeyboardShortcuts.ts
```

- [ ] **Step 2: Update `ProtectedRoute.tsx`**

Replace:
```tsx
"use client";
import { useRouter } from "next/navigation";
```
With:
```tsx
import { useNavigate } from "react-router-dom";
```

Replace `const router = useRouter();` with `const navigate = useNavigate();`

Replace `router.push("/login")` with `navigate("/login", { replace: true })`

- [ ] **Step 3: Update `Sidebar.tsx`**

Replace:
```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
```
With:
```tsx
import { Link, useLocation } from "react-router-dom";
```

Replace `const pathname = usePathname();` with `const { pathname } = useLocation();`

All `<Link href="...">` → `<Link to="...">` (there are multiple in SETTINGS_CHILDREN, MAIN_NAV, and workspace settings link).

- [ ] **Step 4: Update `TopBar.tsx`**

Read the file first. Replace `next/navigation` imports with react-router-dom equivalents using the reference table above.

- [ ] **Step 5: Update `Breadcrumb.tsx`**

Replace `next/link` and `next/navigation` imports. Change `<Link href=...>` → `<Link to=...>`.

- [ ] **Step 6: Update `ChatbotTabNav.tsx`**

Replace `next/link` and `next/navigation` imports. Change `href` → `to` on `<Link>`.

- [ ] **Step 7: Update `CommandPalette.tsx`**

Replace `useRouter` with `useNavigate`. Replace `router.push(...)` with `navigate(...)`.

- [ ] **Step 8: Update `CopilotChat.tsx`**

Replace `useRouter` with `useNavigate`. Replace `router.push(...)` with `navigate(...)`.

- [ ] **Step 9: Update `hooks/useAuth.ts`**

Replace `useRouter` with `useNavigate`. Replace `router.push(...)` with `navigate(...)`.

- [ ] **Step 10: Update `hooks/useKeyboardShortcuts.ts`**

Replace `useRouter` with `useNavigate`. Replace all `router.push(...)` with `navigate(...)`.

- [ ] **Step 11: Run lint to catch any missed imports**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "next/" | head -20
```

Expected: no output (no remaining next/ imports)

- [ ] **Step 12: Commit**

```bash
git add frontend/src/components/ frontend/src/hooks/
git commit -m "refactor: replace next/navigation and next/link with react-router-dom in components and hooks"
```

---

## Chunk 3: Page Components

### Task 4: Auth pages + simple dashboard pages

Update import statements in auth pages and simple dashboard pages (no dynamic params, no complex routing).

**Files:**
- Modify: `frontend/src/app/(auth)/login/page.tsx`
- Modify: `frontend/src/app/(auth)/register/page.tsx`
- Modify: `frontend/src/app/(auth)/accept-invite/page.tsx`
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx`
- Modify: `frontend/src/app/(dashboard)/onboarding/page.tsx` (if exists)
- Modify: `frontend/src/app/(dashboard)/workspaces/page.tsx`

- [ ] **Step 1: Read all files**

```bash
cat "frontend/src/app/(auth)/login/page.tsx"
cat "frontend/src/app/(auth)/register/page.tsx"
cat "frontend/src/app/(auth)/accept-invite/page.tsx"
cat "frontend/src/app/(dashboard)/dashboard/page.tsx"
cat "frontend/src/app/(dashboard)/workspaces/page.tsx"
ls "frontend/src/app/(dashboard)/onboarding/" 2>/dev/null && cat "frontend/src/app/(dashboard)/onboarding/page.tsx"
```

- [ ] **Step 2: Update each file**

For each file:
1. Remove `"use client"` directive (first line)
2. Apply import replacements from the reference table
3. `useSearchParams` — change `const searchParams = useSearchParams()` to `const [searchParams] = useSearchParams()`

**login/page.tsx** specific:
- `process.env.NEXT_PUBLIC_API_URL` → `import.meta.env.VITE_API_URL` (2 occurrences)
- Remove `"use client"`
- `useRouter` → `useNavigate`, `router.push(...)` → `navigate(...)`
- `import Link from 'next/link'` → `import { Link } from 'react-router-dom'`; all `<Link href=...>` → `<Link to=...>`

**register/page.tsx** specific:
- `process.env.NEXT_PUBLIC_API_URL` → `import.meta.env.VITE_API_URL` (1 occurrence)
- Remove `"use client"`
- `useRouter` → `useNavigate`
- `import Link from 'next/link'` → `import { Link } from 'react-router-dom'`; all `<Link href=...>` → `<Link to=...>`

**accept-invite/page.tsx** specific:
- Remove `"use client"`
- `useRouter` → `useNavigate`
- `useSearchParams` — this file uses the variable name `params` (not `searchParams`): change `const params = useSearchParams()` → `const [params] = useSearchParams()`. The `<Suspense>` wrapper can stay as-is.
- `next/link` → `import { Link } from 'react-router-dom'`; all `<Link href=...>` → `<Link to=...>`

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(auth)/" "frontend/src/app/(dashboard)/dashboard/" \
  "frontend/src/app/(dashboard)/workspaces/" "frontend/src/app/(dashboard)/onboarding/"
git commit -m "refactor: update auth and basic dashboard pages to react-router-dom"
```

---

### Task 5: Chatbot pages

Update all chatbot sub-pages (the layout was already handled in Task 2).

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/new/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/settings/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/chat/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/deploy/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/articles/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/sources/page.tsx`

- [ ] **Step 1: Read all files**

```bash
for f in \
  "frontend/src/app/(dashboard)/chatbots/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/new/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/settings/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/chat/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/deploy/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/articles/page.tsx" \
  "frontend/src/app/(dashboard)/chatbots/[id]/sources/page.tsx"; do
  echo "=== $f ===" && cat "$f"
done
```

- [ ] **Step 2: Update each file using the reference table**

For every file:
1. Remove `"use client"`
2. Swap all `next/*` imports
3. `useParams` — React Router `useParams()` returns `string | undefined` per param. If code casts `params.id as string`, change to `const { id } = useParams()` — the cast is still valid.
4. `useRouter` → `useNavigate`, `router.push` → `navigate`

**chatbots/page.tsx** specific:
- `import Link from 'next/link'` → `import { Link } from 'react-router-dom'`; all `<Link href=...>` → `<Link to=...>`

**new/page.tsx** specific (has `useSearchParams`):
- `const searchParams = useSearchParams()` → `const [searchParams] = useSearchParams()`

**deploy/page.tsx** specific (has both env vars):
- `process.env.NEXT_PUBLIC_APP_URL` → `import.meta.env.VITE_APP_URL`
- `process.env.NEXT_PUBLIC_API_URL` → `import.meta.env.VITE_API_URL`

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(dashboard)/chatbots/"
git commit -m "refactor: update chatbot pages to react-router-dom"
```

---

### Task 6: Remaining dashboard pages

Update conversations, intelligence, articles, and settings pages.

**Files:**
- Modify: `frontend/src/app/(dashboard)/conversations/page.tsx`
- Modify: `frontend/src/app/(dashboard)/conversations/[id]/page.tsx`
- Modify: `frontend/src/app/(dashboard)/intelligence/page.tsx`
- Modify: `frontend/src/app/(dashboard)/intelligence/sentiment/page.tsx`
- Modify: `frontend/src/app/(dashboard)/intelligence/gaps/page.tsx`
- Modify: `frontend/src/app/(dashboard)/intelligence/gaps/[id]/page.tsx`
- Modify: `frontend/src/app/(dashboard)/articles/[id]/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/billing/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/data-retention/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/integrations/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/llm/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/security/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/team/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/webhooks/page.tsx`
- Modify: `frontend/src/app/chat/[chatbotId]/page.tsx`

- [ ] **Step 1: Read all files**

```bash
for f in \
  "frontend/src/app/(dashboard)/conversations/page.tsx" \
  "frontend/src/app/(dashboard)/conversations/[id]/page.tsx" \
  "frontend/src/app/(dashboard)/intelligence/page.tsx" \
  "frontend/src/app/(dashboard)/intelligence/sentiment/page.tsx" \
  "frontend/src/app/(dashboard)/intelligence/gaps/page.tsx" \
  "frontend/src/app/(dashboard)/intelligence/gaps/[id]/page.tsx" \
  "frontend/src/app/(dashboard)/articles/[id]/page.tsx" \
  "frontend/src/app/(dashboard)/settings/page.tsx" \
  "frontend/src/app/(dashboard)/settings/billing/page.tsx" \
  "frontend/src/app/(dashboard)/settings/data-retention/page.tsx" \
  "frontend/src/app/(dashboard)/settings/integrations/page.tsx" \
  "frontend/src/app/(dashboard)/settings/llm/page.tsx" \
  "frontend/src/app/(dashboard)/settings/security/page.tsx" \
  "frontend/src/app/(dashboard)/settings/team/page.tsx" \
  "frontend/src/app/(dashboard)/settings/webhooks/page.tsx" \
  "frontend/src/app/chat/[chatbotId]/page.tsx"; do
  echo "=== $f ===" && cat "$f"
done
```

- [ ] **Step 2: Update each file**

For every file:
1. Remove `"use client"`
2. Apply import replacements per the reference table

**conversations/page.tsx** specific (has `useSearchParams`):
- `const searchParams = useSearchParams()` → `const [searchParams] = useSearchParams()`

**intelligence/page.tsx** specific:
- `import Link from 'next/link'` → `import { Link } from 'react-router-dom'`; all `<Link href=...>` → `<Link to=...>`

**settings/integrations/page.tsx** specific (has `useSearchParams`):
- Same `useSearchParams` destructuring change

**settings/page.tsx** specific:
- `process.env.NEXT_PUBLIC_API_URL` → `import.meta.env.VITE_API_URL`

**chat/[chatbotId]/page.tsx** specific:
- `useParams` — `const { chatbotId } = useParams()`

- [ ] **Step 3: Verify no next/ imports remain**

```bash
grep -r "from 'next/" frontend/src/ --include="*.tsx" --include="*.ts" 2>/dev/null
grep -r '"use client"' frontend/src/ --include="*.tsx" --include="*.ts" 2>/dev/null
```

Expected: no output from either command.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/conversations/" \
  "frontend/src/app/(dashboard)/intelligence/" \
  "frontend/src/app/(dashboard)/articles/" \
  "frontend/src/app/(dashboard)/settings/" \
  "frontend/src/app/chat/"
git commit -m "refactor: update remaining dashboard and public pages to react-router-dom"
```

---

## Chunk 4: Environment Variables + Docker + Dependency Install

### Task 7: Environment variable rename and Docker update

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/api-functions.ts`
- Modify: `frontend/src/lib/sse.ts`
- Modify: `frontend/src/components/copilot/api.ts`
- Modify: `docker-compose.yml` (line 96)

Note: `login/page.tsx`, `register/page.tsx`, `deploy/page.tsx`, and `settings/page.tsx` env vars were already handled in Tasks 4-6.

- [ ] **Step 1: Update `frontend/src/lib/api.ts`**

Replace:
```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```
With:
```typescript
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
```

- [ ] **Step 2: Update `frontend/src/lib/api-functions.ts`**

Replace:
```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```
With:
```typescript
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
```

- [ ] **Step 3: Update `frontend/src/lib/sse.ts`**

Same replacement as above.

- [ ] **Step 4: Update `frontend/src/components/copilot/api.ts`**

Same replacement as above.

- [ ] **Step 5: Update `docker-compose.yml`**

Change line 96:
```yaml
- NEXT_PUBLIC_API_URL=http://localhost:8000
```
To:
```yaml
- VITE_API_URL=http://localhost:8000
```

- [ ] **Step 6: Verify all env var usages updated**

```bash
grep -r "NEXT_PUBLIC_" frontend/src/ --include="*.tsx" --include="*.ts" 2>/dev/null
grep -r "process\.env\.NEXT" frontend/src/ --include="*.tsx" --include="*.ts" 2>/dev/null
```

Expected: no output from either command.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api-functions.ts \
  frontend/src/lib/sse.ts frontend/src/components/copilot/api.ts \
  docker-compose.yml
git commit -m "refactor: rename NEXT_PUBLIC_* env vars to VITE_* across frontend"
```

---

### Task 8: Install dependencies and verify build

- [ ] **Step 1: Install dependencies in the running frontend container**

```bash
docker compose exec frontend npm install react-router-dom
docker compose exec frontend npm uninstall next eslint-config-next
docker compose exec frontend npm install --save-dev vite
```

If container is not running or npm fails due to space, do it via bind-mounted volume:
```bash
cd frontend && npm install react-router-dom && npm install --save-dev vite && npm uninstall next eslint-config-next
```

- [ ] **Step 2: TypeScript check — must pass clean**

```bash
docker compose exec frontend npx tsc --noEmit 2>&1 | head -40
```

Expected: no errors, or only pre-existing unrelated errors.

If there are errors about missing `next` module types, they should disappear since we removed all next imports. If new type errors appear, fix them before proceeding.

- [ ] **Step 3: Test suite — must pass**

```bash
docker compose exec frontend npm test 2>&1 | tail -20
```

Expected: all tests pass (Vitest config is Vite-based already, so it should work unchanged).

- [ ] **Step 4: Verify Vite dev server starts**

```bash
docker compose restart frontend
sleep 5
docker compose logs frontend --tail=20
```

Expected: output should contain `VITE v6.x.x  ready in Xms` and `Local: http://0.0.0.0:3000/`

**NOT** expected: `next dev` or any Next.js output.

- [ ] **Step 5: Smoke test in browser**

Open `http://localhost:3001` (docker maps 3001→3000).

Verify:
- Login page loads (not a Next.js error page)
- Can log in with `test@pulse.dev` / `test`
- Dashboard loads with sidebar visible
- Navigate to `/chatbots` — list loads
- Navigate to a chatbot — tabs render, sub-pages work
- HMR works — make a trivial text change to any page component and verify the browser updates in <1 second

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: install react-router-dom and vite, remove next.js dependency"
```

---

## Appendix: Quick Reference for Subagents

### Files that use `useSearchParams` (require tuple destructuring change)
1. `src/app/(auth)/accept-invite/page.tsx`
2. `src/app/(dashboard)/chatbots/new/page.tsx`
3. `src/app/(dashboard)/conversations/page.tsx`
4. `src/app/(dashboard)/settings/integrations/page.tsx`

### Files that use `process.env.NEXT_PUBLIC_API_URL` (handled per task)
1. `src/lib/api.ts` — Task 7
2. `src/lib/api-functions.ts` — Task 7
3. `src/lib/sse.ts` — Task 7
4. `src/components/copilot/api.ts` — Task 7
5. `src/app/(auth)/login/page.tsx` (×2) — Task 4
6. `src/app/(auth)/register/page.tsx` — Task 4
7. `src/app/(dashboard)/settings/page.tsx` — Task 6
8. `src/app/(dashboard)/chatbots/[id]/deploy/page.tsx` — Task 5

### Files that use `process.env.NEXT_PUBLIC_APP_URL`
1. `src/app/(dashboard)/chatbots/[id]/deploy/page.tsx` — Task 5

### Files confirmed to exist (do not skip)
- `frontend/src/app/(dashboard)/chatbots/[id]/settings/page.tsx` — confirmed present, import as `ChatbotSettingsPage`
- `frontend/src/app/(dashboard)/chatbots/[id]/sources/page.tsx` — confirmed present, import as `SourcesPage`; route `<Route path="sources" element={<SourcesPage />} />` is already in the App.tsx above

### Route param names (Next.js `[param]` → React Router `:param`)
| Next.js directory | React Router param |
|---|---|
| `chatbots/[id]/` | `useParams()` → `{ id }` |
| `conversations/[id]/` | `useParams()` → `{ id }` |
| `intelligence/gaps/[id]/` | `useParams()` → `{ id }` |
| `articles/[id]/` | `useParams()` → `{ id }` |
| `chat/[chatbotId]/` | `useParams()` → `{ chatbotId }` |
