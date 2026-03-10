# Pulse Frontend

Next.js 15 (App Router) + TypeScript + Tailwind CSS + Zustand

## Running

### With Docker (recommended)
```bash
# From repo root
make up
# Frontend available at http://localhost:3001
```

### Standalone
```bash
cd frontend
npm install
cp ../.env.example .env.local  # adjust NEXT_PUBLIC_API_URL if needed
npm run dev
# Available at http://localhost:3000
```

## Structure

```
src/
├── app/
│   ├── (auth)/              Login, register pages
│   └── (dashboard)/         All authenticated pages
│       ├── dashboard/        Resolution rate + stats
│       ├── chatbots/         Chatbot list + detail
│       │   └── [id]/
│       │       ├── page.tsx          Sources + Settings tabs
│       │       ├── chat/page.tsx     Test chat (with streaming)
│       │       ├── customize/        Widget customization
│       │       └── deploy/           Embed script, QR, API keys
│       ├── conversations/    Conversation list
│       ├── exceptions/       Escalation queue + detail
│       ├── intelligence/     6 intelligence modules
│       │   ├── gaps/         Doc gap clusters
│       │   ├── topics/       Topic clustering
│       │   ├── sentiment/    Sentiment trends
│       │   ├── features/     Feature request clusters
│       │   └── leads/        Lead scoring feed
│       └── settings/         Billing, integrations, general
├── components/
│   ├── auth/                 ProtectedRoute (handles workspace auto-load)
│   ├── layout/               Sidebar, topbar
│   ├── knowledge/            AddSourceModal
│   └── ui/                   Button, Card, Badge, Input, Spinner
├── lib/
│   ├── api.ts                Axios wrapper with token refresh
│   ├── api-functions.ts      All API calls (workspace-scoped)
│   ├── types.ts              All TypeScript types
│   └── sse.ts                SSE stream for chat
└── stores/
    ├── auth-store.ts         JWT tokens + user
    └── workspace-store.ts    Current workspace selection
```

## Key patterns

### Every API call takes workspaceId first
```ts
import { getChatbots, getConversations } from "@/lib/api-functions";

const workspace = useWorkspaceStore(s => s.currentWorkspace);
const chatbots = await getChatbots(workspace.id);
```

### Workspace is auto-loaded
`ProtectedRoute` fetches workspaces on mount and sets the first one. No page needs to manually fetch workspaces before using `currentWorkspace`.

### Streaming chat
```ts
import { streamChat } from "@/lib/sse";

for await (const event of streamChat(chatbotId, message, { conversationId })) {
  if (event.type === "token") append(event.data);
  if (event.type === "done") setConversationId(event.conversation_id);
}
```

## Environment variables

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend URL (default: `http://localhost:8000`) |
| `NEXT_PUBLIC_APP_URL` | This app's URL (used in deploy page for share links) |

## Tech stack

| Package | Version | Purpose |
|---|---|---|
| Next.js | 15.3.9 | Framework (App Router) |
| React | 19 | UI |
| TypeScript | 5 | Type safety |
| Tailwind CSS | 3 | Styling |
| Zustand | 4 | State (auth + workspace) |
| Recharts | 2 | Dashboard charts |
| Lucide React | latest | Icons |
| clsx | 2 | Conditional classnames |
| react-dropzone | 14 | File upload |
| qrcode.react | 3 | QR codes on deploy page |
| prism-react-renderer | 2 | Syntax highlighting on deploy page |
