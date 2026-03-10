# Testing Phase 5 — Frontend Unit Tests Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Install Vitest + MSW and write unit tests for the frontend's pure-logic modules — `lib/auth.ts`, `lib/api.ts`, both Zustand stores, and the critical data-transform functions in `lib/api-functions.ts`.

**Architecture:** No component rendering — this phase targets pure TypeScript/JavaScript logic only. Tests run in a `happy-dom` environment (provides `localStorage`, `window`, `fetch`) via `vitest`. MSW v2 (`setupServer` from `msw/node`) intercepts `fetch` calls so `ApiClient` and `api-functions` can be tested with realistic HTTP mocking without a live server.

**Tech Stack:** Vitest 2, happy-dom, MSW v2 (`msw/node`), `@vitejs/plugin-react` (needed so Vitest resolves JSX/TS path aliases), `@vitest/coverage-v8`

---

## Context you need

- **Working directory:** `frontend/` (all commands run there unless noted)
- **Run tests in Docker:** `docker compose exec frontend npx vitest run` (the container already has Node/npm)
- **Or run on host:** `cd frontend && npm test` (both work; Vitest is a Node tool)
- **Key files:**
  - `frontend/src/lib/auth.ts` — localStorage token/user helpers
  - `frontend/src/lib/api.ts` — `ApiClient` class (wraps `fetch`)
  - `frontend/src/lib/api-functions.ts` — all API calls + response transforms
  - `frontend/src/stores/auth-store.ts` — Zustand auth state
  - `frontend/src/stores/workspace-store.ts` — Zustand workspace state
  - `frontend/package.json` — add deps + test scripts here
- **Path alias:** `@/` maps to `frontend/src/` — configured in `tsconfig.json`, must also be in `vitest.config.ts`
- **Backend base URL:** `ApiClient` prefixes all paths with `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` — MSW handlers must match `http://localhost:8000/api/v1/...`

## Critical data transforms to test (from `api-functions.ts`)

| Function | Backend response | Frontend output |
|---|---|---|
| `getSentimentTrends` | `{data: [{date, avg_sentiment: null\|number, count}]}` | Computes avg, positive_pct, negative_pct, trend — all `parseFloat(...toFixed(3))` |
| `getExceptions` | `{items: BackendExceptionItem[], total: number}` | `Exception[]` — maps `contact_id/name/email` into nested `contact` object |
| `getExceptionDetail` | `{conversation, messages, contact_context, suggested_action}` | `Exception` — `contact_context` → `contact`, `escalation_reason` from conversation |
| `getCreditsBalance` | `{balance, used_this_month}` | `{balance, usage_this_month, usage_history: []}` — key rename |
| `getConversations` | — | Builds `?status=X&chatbot_id=Y&date_from=Z&date_to=W` params correctly |

---

## Task 1: Vitest Infrastructure

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/test/mocks/server.ts`
- Modify: `Makefile` (root)

**Step 1: Install test dependencies**

```bash
cd frontend && npm install --save-dev \
  vitest@^2.0.0 \
  @vitejs/plugin-react@^4.0.0 \
  @vitest/coverage-v8@^2.0.0 \
  msw@^2.0.0 \
  happy-dom@^14.0.0
```

**Step 2: Add test scripts to `frontend/package.json`**

Add inside `"scripts"`:
```json
"test": "vitest run",
"test:watch": "vitest",
"test:coverage": "vitest run --coverage"
```

**Step 3: Create `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    coverage: {
      reporter: ["text", "html"],
      include: ["src/lib/**", "src/stores/**"],
      exclude: ["src/lib/sse.ts"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

**Step 4: Create `frontend/src/test/mocks/server.ts`**

```typescript
import { setupServer } from "msw/node";
export const server = setupServer();
```

**Step 5: Create `frontend/src/test/setup.ts`**

```typescript
import { afterEach, beforeAll, afterAll } from "vitest";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());
```

**Step 6: Add Makefile targets** (in root `Makefile`)

```makefile
test-frontend:
	docker compose exec frontend npx vitest run

test-frontend-coverage:
	docker compose exec frontend npx vitest run --coverage
```

**Step 7: Smoke test — run with no test files**

```bash
cd frontend && npm test -- --passWithNoTests
```

Expected: `No test files found, exiting with code 0` (or similar pass).

**Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts \
        frontend/src/test/setup.ts frontend/src/test/mocks/server.ts Makefile
git commit -m "test: add Vitest + MSW infra for frontend unit tests"
```

---

## Task 2: `lib/auth.ts` Unit Tests

**Files:**
- Create: `frontend/src/test/lib/auth.test.ts`

The 6 functions in `auth.ts` are pure localStorage wrappers. `happy-dom` provides `localStorage`.

**Step 1: Write the tests**

Create `frontend/src/test/lib/auth.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import {
  getTokens,
  setTokens,
  clearTokens,
  isAuthenticated,
  getCurrentUser,
  setCurrentUser,
} from "@/lib/auth";
import { AuthTokens, User } from "@/lib/types";

const TOKENS: AuthTokens = {
  access_token: "acc.tok.en",
  refresh_token: "ref.tok.en",
  token_type: "bearer",
};

const USER: User = { id: "u1", email: "a@b.com", name: "Alice" };

beforeEach(() => {
  localStorage.clear();
});

// ── getTokens ──────────────────────────────────────────────────────────────

describe("getTokens", () => {
  it("returns null when nothing stored", () => {
    expect(getTokens()).toBeNull();
  });

  it("returns parsed tokens after setTokens", () => {
    setTokens(TOKENS);
    expect(getTokens()).toEqual(TOKENS);
  });

  it("returns null for corrupted JSON", () => {
    localStorage.setItem("pulse_tokens", "not-json");
    expect(getTokens()).toBeNull();
  });
});

// ── setTokens / clearTokens ────────────────────────────────────────────────

describe("setTokens", () => {
  it("persists tokens to localStorage", () => {
    setTokens(TOKENS);
    expect(localStorage.getItem("pulse_tokens")).toBe(JSON.stringify(TOKENS));
  });
});

describe("clearTokens", () => {
  it("removes pulse_tokens key", () => {
    setTokens(TOKENS);
    clearTokens();
    expect(localStorage.getItem("pulse_tokens")).toBeNull();
  });

  it("removes pulse_user key", () => {
    setCurrentUser(USER);
    clearTokens();
    expect(localStorage.getItem("pulse_user")).toBeNull();
  });
});

// ── isAuthenticated ────────────────────────────────────────────────────────

describe("isAuthenticated", () => {
  it("returns false when no tokens", () => {
    expect(isAuthenticated()).toBe(false);
  });

  it("returns true when tokens exist", () => {
    setTokens(TOKENS);
    expect(isAuthenticated()).toBe(true);
  });
});

// ── getCurrentUser / setCurrentUser ───────────────────────────────────────

describe("getCurrentUser", () => {
  it("returns null when nothing stored", () => {
    expect(getCurrentUser()).toBeNull();
  });

  it("returns parsed user after setCurrentUser", () => {
    setCurrentUser(USER);
    expect(getCurrentUser()).toEqual(USER);
  });

  it("returns null for corrupted JSON", () => {
    localStorage.setItem("pulse_user", "{bad}");
    expect(getCurrentUser()).toBeNull();
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test src/test/lib/auth.test.ts
```

Expected: `12 passed`

**Step 3: Commit**

```bash
git add frontend/src/test/lib/auth.test.ts
git commit -m "test: add lib/auth.ts unit tests (12 tests)"
```

---

## Task 3: Zustand Store Unit Tests

**Files:**
- Create: `frontend/src/test/stores/auth-store.test.ts`
- Create: `frontend/src/test/stores/workspace-store.test.ts`

**Important:** Zustand stores are module-level singletons. You must reset their state between tests using `useAuthStore.setState(initialState)` / `useWorkspaceStore.setState(initialState)`. Do NOT import the default initial state — reconstruct it inline.

**Step 1: Create `frontend/src/test/stores/auth-store.test.ts`**

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/stores/auth-store";
import { setTokens, setCurrentUser } from "@/lib/auth";
import { AuthTokens, User } from "@/lib/types";

const TOKENS: AuthTokens = {
  access_token: "acc",
  refresh_token: "ref",
  token_type: "bearer",
};
const USER: User = { id: "u1", email: "a@b.com", name: "Alice" };

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({ user: null, tokens: null, isLoading: true });
});

describe("initialize", () => {
  it("sets isLoading false when no tokens stored", () => {
    useAuthStore.getState().initialize();
    expect(useAuthStore.getState().isLoading).toBe(false);
    expect(useAuthStore.getState().tokens).toBeNull();
  });

  it("loads tokens and user from localStorage", () => {
    setTokens(TOKENS);
    setCurrentUser(USER);
    useAuthStore.getState().initialize();
    expect(useAuthStore.getState().tokens).toEqual(TOKENS);
    expect(useAuthStore.getState().user).toEqual(USER);
  });
});

describe("login", () => {
  it("persists tokens and user in localStorage", () => {
    useAuthStore.getState().login(USER, TOKENS);
    expect(localStorage.getItem("pulse_tokens")).toBe(JSON.stringify(TOKENS));
    expect(localStorage.getItem("pulse_user")).toBe(JSON.stringify(USER));
  });

  it("sets user and tokens in store state", () => {
    useAuthStore.getState().login(USER, TOKENS);
    expect(useAuthStore.getState().user).toEqual(USER);
    expect(useAuthStore.getState().tokens).toEqual(TOKENS);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });
});

describe("logout", () => {
  it("clears store state", () => {
    useAuthStore.getState().login(USER, TOKENS);
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().tokens).toBeNull();
  });

  it("clears localStorage", () => {
    useAuthStore.getState().login(USER, TOKENS);
    useAuthStore.getState().logout();
    expect(localStorage.getItem("pulse_tokens")).toBeNull();
  });
});

describe("setUser", () => {
  it("updates user in state and localStorage", () => {
    const updated: User = { id: "u1", email: "new@b.com", name: "New Name" };
    useAuthStore.getState().setUser(updated);
    expect(useAuthStore.getState().user).toEqual(updated);
    expect(JSON.parse(localStorage.getItem("pulse_user")!)).toEqual(updated);
  });
});
```

**Step 2: Create `frontend/src/test/stores/workspace-store.test.ts`**

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Workspace } from "@/lib/types";

const WS_A: Workspace = { id: "ws-a", name: "Alpha", slug: "alpha", plan: "free" };
const WS_B: Workspace = { id: "ws-b", name: "Beta", slug: "beta", plan: "starter" };

beforeEach(() => {
  useWorkspaceStore.setState({ currentWorkspace: null, workspaces: [] });
});

describe("setCurrentWorkspace", () => {
  it("sets the current workspace", () => {
    useWorkspaceStore.getState().setCurrentWorkspace(WS_A);
    expect(useWorkspaceStore.getState().currentWorkspace).toEqual(WS_A);
  });

  it("replaces a previously set workspace", () => {
    useWorkspaceStore.getState().setCurrentWorkspace(WS_A);
    useWorkspaceStore.getState().setCurrentWorkspace(WS_B);
    expect(useWorkspaceStore.getState().currentWorkspace).toEqual(WS_B);
  });
});

describe("setWorkspaces", () => {
  it("stores a list of workspaces", () => {
    useWorkspaceStore.getState().setWorkspaces([WS_A, WS_B]);
    expect(useWorkspaceStore.getState().workspaces).toHaveLength(2);
  });

  it("replaces the existing list", () => {
    useWorkspaceStore.getState().setWorkspaces([WS_A, WS_B]);
    useWorkspaceStore.getState().setWorkspaces([WS_A]);
    expect(useWorkspaceStore.getState().workspaces).toHaveLength(1);
    expect(useWorkspaceStore.getState().workspaces[0]).toEqual(WS_A);
  });
});
```

**Step 3: Run tests**

```bash
cd frontend && npm test src/test/stores/
```

Expected: `10 passed`

**Step 4: Commit**

```bash
git add frontend/src/test/stores/
git commit -m "test: add Zustand store unit tests (10 tests)"
```

---

## Task 4: `lib/api.ts` ApiClient Unit Tests

**Files:**
- Create: `frontend/src/test/lib/api.test.ts`

`ApiClient` wraps `fetch`. MSW intercepts `fetch` calls at the network level. All handlers match `http://localhost:8000/api/v1/...` (default `BASE_URL`). The `ApiClient` instance is `api` exported from `lib/api.ts` — import and call it directly.

**Step 1: Write the tests**

Create `frontend/src/test/lib/api.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { api, ApiError } from "@/lib/api";
import { setTokens, clearTokens } from "@/lib/auth";
import { AuthTokens } from "@/lib/types";

const TOKENS: AuthTokens = {
  access_token: "test-access-token",
  refresh_token: "test-refresh-token",
  token_type: "bearer",
};

const BASE = "http://localhost:8000";

beforeEach(() => {
  clearTokens();
});

// ── Basic GET ──────────────────────────────────────────────────────────────

describe("api.get", () => {
  it("returns parsed JSON on 200", async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json({ hello: "world" }),
      ),
    );
    const result = await api.get("/api/v1/test");
    expect(result).toEqual({ hello: "world" });
  });

  it("includes Authorization header when tokens set", async () => {
    setTokens(TOKENS);
    let captured: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/test`, ({ request }) => {
        captured = request.headers.get("authorization");
        return HttpResponse.json({});
      }),
    );
    await api.get("/api/v1/test");
    expect(captured).toBe(`Bearer ${TOKENS.access_token}`);
  });

  it("throws ApiError on 4xx", async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );
    await expect(api.get("/api/v1/test")).rejects.toBeInstanceOf(ApiError);
  });

  it("ApiError carries the status code", async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        new HttpResponse(null, { status: 422 }),
      ),
    );
    try {
      await api.get("/api/v1/test");
    } catch (e) {
      expect((e as ApiError).status).toBe(422);
    }
  });
});

// ── DELETE returns undefined on 204 ───────────────────────────────────────

describe("api.delete", () => {
  it("returns undefined for 204 No Content", async () => {
    server.use(
      http.delete(`${BASE}/api/v1/test/1`, () =>
        new HttpResponse(null, { status: 204 }),
      ),
    );
    const result = await api.delete("/api/v1/test/1");
    expect(result).toBeUndefined();
  });
});

// ── POST / PUT ────────────────────────────────────────────────────────────

describe("api.post", () => {
  it("sends JSON body", async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/api/v1/test`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ok: true });
      }),
    );
    await api.post("/api/v1/test", { key: "value" });
    expect(body).toEqual({ key: "value" });
  });
});

// ── 401 → refresh → retry ─────────────────────────────────────────────────

describe("401 token refresh", () => {
  it("retries with new token after successful refresh", async () => {
    setTokens(TOKENS);
    let callCount = 0;

    server.use(
      // First call returns 401
      http.get(`${BASE}/api/v1/protected`, () => {
        callCount++;
        if (callCount === 1) {
          return new HttpResponse(null, { status: 401 });
        }
        return HttpResponse.json({ data: "secret" });
      }),
      // Refresh returns new token
      http.post(`${BASE}/api/v1/auth/refresh`, () =>
        HttpResponse.json({
          access_token: "new-access-token",
          refresh_token: "new-refresh-token",
          token_type: "bearer",
        }),
      ),
    );

    const result = await api.get("/api/v1/protected");
    expect(result).toEqual({ data: "secret" });
    expect(callCount).toBe(2);
  });

  it("throws ApiError 401 when refresh fails", async () => {
    setTokens(TOKENS);
    server.use(
      http.get(`${BASE}/api/v1/protected`, () =>
        new HttpResponse(null, { status: 401 }),
      ),
      http.post(`${BASE}/api/v1/auth/refresh`, () =>
        new HttpResponse(null, { status: 401 }),
      ),
    );

    await expect(api.get("/api/v1/protected")).rejects.toMatchObject({
      status: 401,
    });
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test src/test/lib/api.test.ts
```

Expected: `8 passed`

**Note on the 401 refresh test:** `window.location.href = "/login"` runs during the failing-refresh path. In `happy-dom` this is a no-op or may log a warning — that's fine, just ensure the test still passes and throws the expected error.

**Step 3: Commit**

```bash
git add frontend/src/test/lib/api.test.ts
git commit -m "test: add ApiClient unit tests — 401 retry, refresh, 204 (8 tests)"
```

---

## Task 5: `lib/api-functions.ts` Transform Tests

**Files:**
- Create: `frontend/src/test/lib/api-functions.test.ts`

These are the highest-value tests: they cover the documented backend↔frontend shape mismatches.

Each test function:
1. Registers an MSW handler that returns a controlled backend response
2. Calls the api-function
3. Asserts the transformed output shape

**Step 1: Write the tests**

Create `frontend/src/test/lib/api-functions.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import {
  getSentimentTrends,
  getExceptions,
  getExceptionDetail,
  getCreditsBalance,
  getConversations,
} from "@/lib/api-functions";
import { setTokens } from "@/lib/auth";

const WS = "ws-test-id";
const BASE = `http://localhost:8000/api/v1/workspaces/${WS}`;
const TOKENS = {
  access_token: "tok",
  refresh_token: "ref",
  token_type: "bearer",
};

beforeEach(() => {
  setTokens(TOKENS);
});

// ── getCreditsBalance ──────────────────────────────────────────────────────

describe("getCreditsBalance", () => {
  it("maps used_this_month → usage_this_month", async () => {
    server.use(
      http.get(`${BASE}/credits/balance`, () =>
        HttpResponse.json({ balance: 500, used_this_month: 120 }),
      ),
    );
    const result = await getCreditsBalance(WS);
    expect(result.balance).toBe(500);
    expect(result.usage_this_month).toBe(120);
    expect(result.usage_history).toEqual([]);
  });

  it("defaults usage_this_month to 0 when missing", async () => {
    server.use(
      http.get(`${BASE}/credits/balance`, () =>
        HttpResponse.json({ balance: 100, used_this_month: undefined }),
      ),
    );
    const result = await getCreditsBalance(WS);
    expect(result.usage_this_month).toBe(0);
  });
});

// ── getConversations URL params ────────────────────────────────────────────

describe("getConversations", () => {
  it("calls /conversations with no params when no filters", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/conversations`, ({ request }) => {
        url = request.url;
        return HttpResponse.json([]);
      }),
    );
    await getConversations(WS);
    expect(url).not.toContain("status=");
    expect(url).not.toContain("chatbot_id=");
  });

  it("appends status filter to URL", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/conversations`, ({ request }) => {
        url = request.url;
        return HttpResponse.json([]);
      }),
    );
    await getConversations(WS, { status: "open" });
    expect(url).toContain("status=open");
  });

  it("appends chatbot_id filter to URL", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/conversations`, ({ request }) => {
        url = request.url;
        return HttpResponse.json([]);
      }),
    );
    await getConversations(WS, { chatbot_id: "bot-1" });
    expect(url).toContain("chatbot_id=bot-1");
  });

  it("appends date_from and date_to filters", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/conversations`, ({ request }) => {
        url = request.url;
        return HttpResponse.json([]);
      }),
    );
    await getConversations(WS, {
      date_from: "2026-01-01",
      date_to: "2026-01-31",
    });
    expect(url).toContain("date_from=2026-01-01");
    expect(url).toContain("date_to=2026-01-31");
  });
});

// ── getExceptions ──────────────────────────────────────────────────────────

describe("getExceptions", () => {
  const backendItem = {
    id: "conv-1",
    workspace_id: WS,
    chatbot_id: "bot-1",
    chatbot_name: "Support Bot",
    contact_id: "c-1",
    contact_name: "Alice",
    contact_email: "alice@example.com",
    escalation_reason: "low_confidence",
    confidence_avg: 0.42,
    status: "open",
    last_message_preview: "Hello",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T01:00:00Z",
  };

  it("maps items array to Exception[]", async () => {
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [backendItem], total: 1 }),
      ),
    );
    const result = await getExceptions(WS);
    expect(result).toHaveLength(1);
  });

  it("maps conversation fields correctly", async () => {
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [backendItem], total: 1 }),
      ),
    );
    const [exc] = await getExceptions(WS);
    expect(exc.conversation.id).toBe("conv-1");
    expect(exc.conversation.chatbot_id).toBe("bot-1");
    expect(exc.conversation.status).toBe("open");
  });

  it("maps contact when name/email present", async () => {
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [backendItem], total: 1 }),
      ),
    );
    const [exc] = await getExceptions(WS);
    expect(exc.contact).toBeDefined();
    expect(exc.contact!.name).toBe("Alice");
    expect(exc.contact!.email).toBe("alice@example.com");
  });

  it("sets contact to undefined when no name or email", async () => {
    const anonymousItem = {
      ...backendItem,
      contact_name: undefined,
      contact_email: undefined,
    };
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [anonymousItem], total: 1 }),
      ),
    );
    const [exc] = await getExceptions(WS);
    expect(exc.contact).toBeUndefined();
  });

  it("defaults escalation_reason to empty string when missing", async () => {
    const noReason = { ...backendItem, escalation_reason: undefined };
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [noReason], total: 1 }),
      ),
    );
    const [exc] = await getExceptions(WS);
    expect(exc.escalation_reason).toBe("");
  });
});

// ── getExceptionDetail ─────────────────────────────────────────────────────

describe("getExceptionDetail", () => {
  const backendDetail = {
    conversation: {
      id: "conv-2",
      workspace_id: WS,
      chatbot_id: "bot-1",
      chatbot_name: "Bot",
      escalation_reason: "human_requested",
      confidence_avg: 0.3,
      status: "open",
      created_at: "2026-01-02T00:00:00Z",
      updated_at: "2026-01-02T01:00:00Z",
    },
    messages: [],
    contact_context: {
      id: "c-2",
      name: "Bob",
      email: "bob@example.com",
      lead_score: 55,
      lead_tier: "hot",
    },
    suggested_action: "offer_demo",
  };

  it("maps contact_context to contact field", async () => {
    server.use(
      http.get(`${BASE}/exceptions/conv-2`, () =>
        HttpResponse.json(backendDetail),
      ),
    );
    const exc = await getExceptionDetail(WS, "conv-2");
    expect(exc.contact).toBeDefined();
    expect(exc.contact!.id).toBe("c-2");
    expect(exc.contact!.name).toBe("Bob");
    expect(exc.contact!.lead_score).toBe(55);
    expect(exc.contact!.lead_tier).toBe("hot");
  });

  it("maps escalation_reason from conversation", async () => {
    server.use(
      http.get(`${BASE}/exceptions/conv-2`, () =>
        HttpResponse.json(backendDetail),
      ),
    );
    const exc = await getExceptionDetail(WS, "conv-2");
    expect(exc.escalation_reason).toBe("human_requested");
  });

  it("passes suggested_action through", async () => {
    server.use(
      http.get(`${BASE}/exceptions/conv-2`, () =>
        HttpResponse.json(backendDetail),
      ),
    );
    const exc = await getExceptionDetail(WS, "conv-2");
    expect(exc.suggested_action).toBe("offer_demo");
  });

  it("sets contact to undefined when no contact_context", async () => {
    const noContact = { ...backendDetail, contact_context: undefined };
    server.use(
      http.get(`${BASE}/exceptions/conv-2`, () =>
        HttpResponse.json(noContact),
      ),
    );
    const exc = await getExceptionDetail(WS, "conv-2");
    expect(exc.contact).toBeUndefined();
  });
});

// ── getSentimentTrends ─────────────────────────────────────────────────────

describe("getSentimentTrends", () => {
  it("computes avg_sentiment correctly", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: 0.6, count: 5 },
            { date: "2026-01-02", avg_sentiment: 0.4, count: 3 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "7d");
    // avg of 0.6 + 0.4 = 1.0 / 2 = 0.5
    expect(result.avg_sentiment).toBe(0.5);
  });

  it("computes positive_pct (score >= 0.3)", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: 0.8, count: 1 },
            { date: "2026-01-02", avg_sentiment: 0.1, count: 1 },
            { date: "2026-01-03", avg_sentiment: -0.5, count: 1 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "30d");
    // 1 out of 3 is < 0.3, so positive = 2/3 * 100 ≈ 66.67
    expect(result.positive_pct).toBeCloseTo(66.67, 1);
  });

  it("computes negative_pct (score <= -0.3)", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: 0.5, count: 1 },
            { date: "2026-01-02", avg_sentiment: -0.5, count: 1 },
            { date: "2026-01-03", avg_sentiment: -0.8, count: 1 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "30d");
    // 2 out of 3 negative
    expect(result.negative_pct).toBeCloseTo(66.67, 1);
  });

  it("computes trend as last - first score", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: 0.2, count: 1 },
            { date: "2026-01-02", avg_sentiment: 0.7, count: 1 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "7d");
    // 0.7 - 0.2 = 0.5
    expect(result.trend).toBeCloseTo(0.5, 3);
  });

  it("filters out null avg_sentiment data points", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: null, count: 0 },
            { date: "2026-01-02", avg_sentiment: 0.6, count: 2 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "7d");
    expect(result.data_points).toHaveLength(1);
    expect(result.avg_sentiment).toBe(0.6);
  });

  it("returns zeros for empty data", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    const result = await getSentimentTrends(WS, "7d");
    expect(result.avg_sentiment).toBe(0);
    expect(result.positive_pct).toBe(0);
    expect(result.negative_pct).toBe(0);
    expect(result.trend).toBe(0);
  });

  it("passes correct days param for range strings", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/sentiment-trends`, ({ request }) => {
        url = request.url;
        return HttpResponse.json({ data: [] });
      }),
    );
    await getSentimentTrends(WS, "90d");
    expect(url).toContain("days=90");
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test src/test/lib/api-functions.test.ts
```

Expected: `20 passed`

**Step 3: Run full frontend test suite**

```bash
cd frontend && npm test
```

Expected: `50 passed` (12 + 10 + 8 + 20)

**Step 4: Commit**

```bash
git add frontend/src/test/lib/api-functions.test.ts
git commit -m "test: add api-functions transform unit tests (20 tests)"
```

---

## Task 6: Wire Up Coverage + Final Verify

**Files:**
- Modify: `Makefile`

**Step 1: Run coverage report**

```bash
cd frontend && npm run test:coverage
```

Expected: passes, coverage report printed to terminal. Target files: `src/lib/auth.ts`, `src/lib/api.ts`, `src/lib/api-functions.ts`, `src/stores/auth-store.ts`, `src/stores/workspace-store.ts`.

**Step 2: Run full backend + frontend suites together**

```bash
docker compose exec backend bash -c "cd /app && pytest tests/ -q 2>&1 | tail -3"
cd frontend && npm test
```

Expected: backend `234 passed`, frontend `~50 passed`.

**Step 3: Final commit**

```bash
git add Makefile
git commit -m "test: Phase 5 complete — 50 frontend unit tests (Vitest + MSW)"
```

---

## Summary

| Task | File | Tests |
|---|---|---|
| T1 | Vitest infra | 0 (setup only) |
| T2 | lib/auth.ts | 12 |
| T3 | Zustand stores | 10 |
| T4 | lib/api.ts ApiClient | 8 |
| T5 | lib/api-functions.ts transforms | 20 |
| **Total** | | **~50** |
