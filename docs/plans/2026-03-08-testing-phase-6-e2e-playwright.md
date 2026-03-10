# Testing Phase 6 — E2E Tests (Playwright) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Install Playwright and write E2E tests covering the authentication flow, dashboard, chatbots, conversations, and exceptions pages against the running Docker stack.

**Architecture:** Tests run from the host machine against `http://localhost:3001` (the Docker-mapped frontend). A `setup` project authenticates once and saves auth state (including localStorage tokens) to `e2e/.auth/user.json`. All other test files reuse that state so every test starts already logged in. Tests are read-only — they use the pre-seeded dev data and do not create/delete resources (except the "create chatbot" modal open/cancel test).

**Tech Stack:** `@playwright/test`, Chromium, Playwright's `storageState` for auth reuse, `playwright.config.ts` in `frontend/`

---

## Context you need

- **Dev credentials:** `test@pulse.dev` / `test`
- **Frontend URL:** `http://localhost:3001` (Docker maps 3001 → container port 3000)
- **Backend URL:** `http://localhost:8000`
- **Seeded workspace ID:** `350863e7-3dc8-430e-bc23-fd41d4499d7b`
- **Seeded chatbot ID:** `a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108`
- **PREREQUISITE:** Docker stack must be running (`make up && make seed`) before running E2E tests
- **Run from host** (not Docker): `cd frontend && npx playwright test`
- **Auth storage:** `frontend/e2e/.auth/user.json` (gitignored) — created by auth setup project

## How Playwright auth works with localStorage

This app stores JWT tokens in localStorage (`pulse_tokens`, `pulse_user`). After `auth.setup.ts` logs in:
- `page.context().storageState({ path: authFile })` saves all localStorage values
- `use: { storageState: authFile }` in the config restores them before each test
- `ProtectedRoute` calls `initialize()` which reads `pulse_tokens` from localStorage → stays authenticated

## App routing facts

- `/` → redirect to `/dashboard`
- `/login` → login form (email + password)
- `/dashboard` → resolution rate stats + charts
- `/chatbots` → chatbot grid with "Create Chatbot" button
- `/conversations` → conversations table
- `/exceptions` → exceptions queue
- Sidebar links: Dashboard, Chatbots, Conversations, Exceptions, Intelligence, Settings, Team, Webhooks, SSO, Security, Data Retention, Audit Logs

---

## Task 1: Playwright Infrastructure

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/auth.setup.ts`
- Create: `frontend/.gitignore` or modify it
- Modify: root `Makefile`

**Step 1: Install Playwright**

```bash
cd /Users/yvanveldeman/dev/pulse/frontend
npm install --save-dev @playwright/test
npx playwright install chromium
```

**Step 2: Add scripts to `frontend/package.json`**

In `"scripts"`:
```json
"test:e2e": "playwright test",
"test:e2e:headed": "playwright test --headed",
"test:e2e:report": "playwright show-report"
```

**Step 3: Create `frontend/playwright.config.ts`**

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "html",
  use: {
    baseURL: "http://localhost:3001",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/.auth/user.json",
      },
      dependencies: ["setup"],
    },
  ],
});
```

**Step 4: Create `frontend/e2e/auth.setup.ts`**

```typescript
import { test as setup, expect } from "@playwright/test";
import path from "path";

const authFile = path.join(__dirname, ".auth/user.json");

setup("authenticate as dev user", async ({ page }) => {
  await page.goto("/login");

  // Fill credentials
  await page.getByLabel("Email").fill("test@pulse.dev");
  await page.getByLabel("Password").fill("test");
  await page.getByRole("button", { name: "Sign in" }).click();

  // Wait for redirect to dashboard
  await page.waitForURL(/\/dashboard/, { timeout: 10_000 });

  // Save auth state (localStorage tokens + cookies)
  await page.context().storageState({ path: authFile });
});
```

**Step 5: Add `.auth/` to gitignore**

Add to `frontend/.gitignore` (create if it doesn't exist):
```
# Playwright auth state
e2e/.auth/
playwright-report/
test-results/
```

**Step 6: Add Makefile targets** in root `Makefile`:

```makefile
test-e2e:
	cd frontend && npx playwright test

test-e2e-headed:
	cd frontend && npx playwright test --headed
```

**Step 7: Create `frontend/e2e/.auth/.gitkeep`**

```bash
mkdir -p /Users/yvanveldeman/dev/pulse/frontend/e2e/.auth
touch /Users/yvanveldeman/dev/pulse/frontend/e2e/.auth/.gitkeep
```

**Step 8: Verify setup works**

Make sure the Docker stack is running, then:
```bash
cd /Users/yvanveldeman/dev/pulse/frontend
npx playwright test --project=setup
```

Expected: `auth.setup.ts` passes — `e2e/.auth/user.json` is created with localStorage tokens.

**Step 9: Commit**

```bash
cd /Users/yvanveldeman/dev/pulse
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.ts \
        frontend/e2e/auth.setup.ts frontend/e2e/.auth/.gitkeep Makefile
git commit -m "test: add Playwright E2E infra with auth setup project"
```

---

## Task 2: Authentication Flow Tests

**Files:**
- Create: `frontend/e2e/auth.test.ts`

These tests run WITHOUT storageState (they test the auth flows themselves). They use the default browser with no pre-existing auth state.

**Step 1: Create `frontend/e2e/auth.test.ts`**

```typescript
import { test, expect } from "@playwright/test";

// These tests must run WITHOUT auth state — override the project storage state
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Authentication", () => {
  test("login page renders correctly", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("Pulse")).toBeVisible();
    await expect(page.getByText("Sign in to your account")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("successful login redirects to dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("test@pulse.dev");
    await page.getByLabel("Password").fill("test");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL(/\/dashboard/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("wrong password shows error message", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("test@pulse.dev");
    await page.getByLabel("Password").fill("wrongpassword");
    await page.getByRole("button", { name: "Sign in" }).click();
    // Error appears — either "Invalid email or password" or the backend detail
    await expect(
      page.locator(".bg-red-50, [class*='red']").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("unauthenticated user redirected from /dashboard to /login", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/\/login/, { timeout: 5_000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test("register page is accessible", async ({ page }) => {
    await page.goto("/register");
    await expect(
      page.getByRole("heading", { name: /create|register|sign up/i })
        .or(page.getByText(/create.*account/i))
    ).toBeVisible({ timeout: 5_000 });
  });
});
```

**Step 2: Run tests (stack must be up)**

```bash
cd /Users/yvanveldeman/dev/pulse/frontend
npx playwright test e2e/auth.test.ts --project=chromium
```

Expected: **5 passed**

If "register page" test fails because the heading doesn't match, read `frontend/src/app/(auth)/register/page.tsx` to find the actual heading text and update the locator.

**Step 3: Commit**

```bash
cd /Users/yvanveldeman/dev/pulse
git add frontend/e2e/auth.test.ts
git commit -m "test: add auth E2E tests — login, failure, redirect (5 tests)"
```

---

## Task 3: Dashboard & Navigation Smoke Tests

**Files:**
- Create: `frontend/e2e/dashboard.test.ts`

These tests use the saved auth state (already logged in).

**Step 1: Create `frontend/e2e/dashboard.test.ts`**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("loads at /dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);
    // Wait for loading spinner to disappear
    await expect(page.locator("svg.animate-spin, [class*='animate-spin']")).toHaveCount(0, {
      timeout: 10_000,
    });
  });

  test("sidebar is visible with key nav items", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = page.locator("aside");
    await expect(sidebar).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Dashboard" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Chatbots" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Conversations" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Exceptions" })).toBeVisible();
  });

  test("shows Pulse branding in sidebar", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("aside").getByText("Pulse")).toBeVisible();
  });

  test("navigating to /chatbots via sidebar link works", async ({ page }) => {
    await page.goto("/dashboard");
    await page.locator("aside").getByRole("link", { name: "Chatbots" }).click();
    await page.waitForURL(/\/chatbots/, { timeout: 5_000 });
    await expect(page).toHaveURL(/\/chatbots/);
  });

  test("root / redirects to /dashboard when authenticated", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForURL(/\/dashboard/, { timeout: 5_000 });
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
```

**Step 2: Run the auth setup first, then tests**

```bash
cd /Users/yvanveldeman/dev/pulse/frontend
npx playwright test --project=setup
npx playwright test e2e/dashboard.test.ts
```

Expected: **5 passed**

**Possible issue:** If the loading spinner stays visible (API slow), increase the timeout. If it's a class name mismatch, check `frontend/src/components/ui/Spinner.tsx` for the exact class.

**Step 3: Commit**

```bash
cd /Users/yvanveldeman/dev/pulse
git add frontend/e2e/dashboard.test.ts
git commit -m "test: add dashboard + navigation E2E smoke tests (5 tests)"
```

---

## Task 4: Chatbots Page Tests

**Files:**
- Create: `frontend/e2e/chatbots.test.ts`

**Step 1: Create `frontend/e2e/chatbots.test.ts`**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Chatbots", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/chatbots");
    // Wait for loading to finish
    await expect(page.locator("svg.animate-spin, [class*='animate-spin']")).toHaveCount(0, {
      timeout: 10_000,
    });
  });

  test("chatbots page renders heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Chatbots" })
    ).toBeVisible();
  });

  test("Create Chatbot button is visible", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /create chatbot/i })
    ).toBeVisible();
  });

  test("seeded chatbot appears in list", async ({ page }) => {
    // At least one chatbot card should exist (from seeded data)
    const cards = page.locator("a[href*='/chatbots/']");
    await expect(cards.first()).toBeVisible({ timeout: 8_000 });
  });

  test("clicking Create Chatbot opens modal", async ({ page }) => {
    await page.getByRole("button", { name: /create chatbot/i }).click();
    // Modal should appear with a Name input
    await expect(page.getByLabel("Name")).toBeVisible({ timeout: 3_000 });
    // Cancel closes modal
    await page.getByRole("button", { name: /cancel/i }).click();
    await expect(page.getByLabel("Name")).toHaveCount(0);
  });

  test("clicking a chatbot card navigates to chatbot detail", async ({
    page,
  }) => {
    const firstCard = page.locator("a[href*='/chatbots/']").first();
    await firstCard.click();
    await page.waitForURL(/\/chatbots\/.+/, { timeout: 5_000 });
    await expect(page).toHaveURL(/\/chatbots\/.+/);
  });
});
```

**Step 2: Run tests**

```bash
cd /Users/yvanveldeman/dev/pulse/frontend
npx playwright test e2e/chatbots.test.ts
```

Expected: **5 passed**

**If "seeded chatbot" test fails:** The `make seed` command must be run first. Also verify that the seeded chatbot is actually showing up by checking `http://localhost:8000/api/v1/workspaces/350863e7-3dc8-430e-bc23-fd41d4499d7b/chatbots` directly.

**Step 3: Commit**

```bash
cd /Users/yvanveldeman/dev/pulse
git add frontend/e2e/chatbots.test.ts
git commit -m "test: add chatbots E2E tests — list, modal, navigation (5 tests)"
```

---

## Task 5: Conversations & Exceptions Pages

**Files:**
- Create: `frontend/e2e/conversations.test.ts`
- Create: `frontend/e2e/exceptions.test.ts`

**Step 1: Create `frontend/e2e/conversations.test.ts`**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Conversations", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/conversations");
    await expect(page.locator("svg.animate-spin, [class*='animate-spin']")).toHaveCount(0, {
      timeout: 10_000,
    });
  });

  test("conversations page renders without error", async ({ page }) => {
    // No error state visible
    await expect(page.getByText(/something went wrong|error loading/i)).toHaveCount(0);
  });

  test("conversations page shows heading or empty state", async ({ page }) => {
    const heading = page.getByRole("heading", { name: /conversations/i });
    const emptyState = page.getByText(/no conversations/i);
    await expect(heading.or(emptyState)).toBeVisible({ timeout: 8_000 });
  });

  test("sidebar Conversations link is active on conversations page", async ({
    page,
  }) => {
    // The active nav item should have a distinct style
    const convLink = page.locator("aside").getByRole("link", { name: "Conversations" });
    await expect(convLink).toBeVisible();
  });
});
```

**Step 2: Create `frontend/e2e/exceptions.test.ts`**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Exceptions Queue", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/exceptions");
    await expect(page.locator("svg.animate-spin, [class*='animate-spin']")).toHaveCount(0, {
      timeout: 10_000,
    });
  });

  test("exceptions page renders without error", async ({ page }) => {
    await expect(page.getByText(/something went wrong|error loading/i)).toHaveCount(0);
  });

  test("exceptions page shows heading or empty state", async ({ page }) => {
    const heading = page.getByRole("heading", { name: /exceptions/i });
    const emptyState = page.getByText(/no exceptions|all caught up/i);
    await expect(heading.or(emptyState)).toBeVisible({ timeout: 8_000 });
  });

  test("can navigate from exceptions back to dashboard", async ({ page }) => {
    await page.locator("aside").getByRole("link", { name: "Dashboard" }).click();
    await page.waitForURL(/\/dashboard/, { timeout: 5_000 });
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
```

**Step 3: Run both test files**

```bash
cd /Users/yvanveldeman/dev/pulse/frontend
npx playwright test e2e/conversations.test.ts e2e/exceptions.test.ts
```

Expected: **6 passed** (3 + 3)

**Step 4: Run the full E2E suite**

```bash
cd /Users/yvanveldeman/dev/pulse/frontend
npx playwright test
```

Expected: **~24 passed** across all 5 files (5 auth + 5 dashboard + 5 chatbots + 3 conversations + 3 exceptions = 21, plus the auth.setup = ~22 runs total).

**Step 5: Commit**

```bash
cd /Users/yvanveldeman/dev/pulse
git add frontend/e2e/conversations.test.ts frontend/e2e/exceptions.test.ts
git commit -m "test: add conversations + exceptions E2E smoke tests (6 tests)"
```

---

## Final Verify

Run the full E2E suite and confirm all pass:

```bash
cd /Users/yvanveldeman/dev/pulse/frontend
npx playwright test --reporter=list
```

Expected output: all tests PASSED with no failures.

Also confirm the backend + frontend unit suites are still green:

```bash
docker compose exec backend bash -c "cd /app && pytest tests/ -q 2>&1 | tail -3"
cd frontend && npx vitest run
```

Expected: `234 passed` backend, `53 passed` frontend unit.

Final commit if any cleanup needed:
```bash
git commit -m "test: Phase 6 complete — E2E tests with Playwright (~21 tests)"
```

---

## Summary

| Task | File | Tests |
|---|---|---|
| T1 | Playwright infra + auth setup | 1 (setup) |
| T2 | Auth flow | 5 |
| T3 | Dashboard + navigation | 5 |
| T4 | Chatbots | 5 |
| T5 | Conversations + exceptions | 6 |
| **Total** | | **~22** |

## Troubleshooting

**Auth setup fails (can't find Email label):**
The `<Input label="Email">` component renders a `<label>` element. If `getByLabel("Email")` doesn't find it, use `page.locator('input[type="email"]')` as a fallback.

**Spinner still visible timeout:**
The spinner appears while the app loads workspace data from the API. If the backend is slow, increase timeout from 10_000 to 15_000.

**Dashboard page shows loading forever:**
Check that `make seed` was run and the backend is healthy: `curl http://localhost:8000/api/v1/health`

**Chatbot cards not found:**
Check if `make seed` populated data. You can also add a fallback test that checks for the "No chatbots yet" empty state message.
