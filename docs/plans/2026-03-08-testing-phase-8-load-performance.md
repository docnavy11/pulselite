# Phase 8 — Load & Performance Tests (k6) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Write three k6 load-test scenarios covering the health endpoint, authenticated dashboard reads, and the public widget-config endpoint, with thresholds that enforce p95 < 500ms and error rate < 1%, gated via `make perf-all`.

**Architecture:** k6 scripts live in `k6/` at the repo root (not in the backend — load tests are infrastructure-level, not unit tests). Each scenario is a standalone `.js` file parameterized by env vars (`BASE_URL`, `WS_ID`, `CHATBOT_ID`, `EMAIL`, `PASSWORD`) so they work against any environment. Thresholds are embedded in each script; CI can run `make perf-smoke` for a quick gate or `make perf-all` for the full suite.

**Tech Stack:** k6 (Homebrew install on macOS), JavaScript (k6 scripting DSL), GNU Make

---

## Context

- Backend: `http://localhost:8000`
- Dev credentials: `test@pulse.dev` / `test`
- Dev workspace ID: `350863e7-3dc8-430e-bc23-fd41d4499d7b`
- Dev chatbot ID: `a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108`
- Auth: POST `/api/v1/auth/login` → `{tokens: {access_token}}` → `Authorization: Bearer <token>`
- Public widget config: `GET /api/v1/widget/{chatbot_id}/config` (no auth)
- Dashboard: `GET /api/v1/workspaces/{workspace_id}/dashboard`
- Chatbots list: `GET /api/v1/workspaces/{workspace_id}/chatbots`
- Health: `GET /api/v1/health`

---

### Task 1: Install k6 + health smoke scenario

**Files:**
- Create: `k6/smoke.js`
- Modify: `Makefile`

**Step 1: Install k6**

```bash
brew install k6
k6 version
```

Expected: prints `k6 v0.xx.0 ...`

**Step 2: Create `k6/` directory and `k6/smoke.js`**

```bash
mkdir -p k6
```

Create `k6/smoke.js`:

```javascript
// k6/smoke.js
// Smoke test: health endpoint only. 5 VUs, 20s.
// Validates p95 < 200ms, error rate < 1%.
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

export const options = {
  vus: 5,
  duration: "20s",
  thresholds: {
    http_req_duration: ["p(95)<200"],
    errors: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const res = http.get(`${BASE_URL}/api/v1/health`);
  const ok = check(res, {
    "status is 200": (r) => r.status === 200,
    "database connected": (r) => {
      try {
        return JSON.parse(r.body).database === "connected";
      } catch {
        return false;
      }
    },
  });
  errorRate.add(!ok);
  sleep(0.5);
}
```

**Step 3: Run the smoke test**

```bash
k6 run k6/smoke.js
```

Expected output:
- `✓ status is 200`
- `✓ database connected`
- `http_req_duration p(95) < 200ms` ✓
- `errors rate < 1%` ✓
- Script exits 0.

If exit is non-zero, check Docker containers are up (`docker compose ps`).

**Step 4: Add `perf-smoke` target to Makefile**

Read the Makefile first. Add after `lint-security-static:`:

```makefile
perf-smoke:
	k6 run k6/smoke.js

perf-auth:
	k6 run k6/auth-read.js

perf-widget:
	k6 run k6/widget.js

perf-all: perf-smoke perf-auth perf-widget
```

Update `.PHONY` to include: `perf-smoke perf-auth perf-widget perf-all`

**Step 5: Commit**

```bash
git add k6/smoke.js Makefile
git commit -m "perf: add k6 smoke test for health endpoint"
```

---

### Task 2: Authenticated read scenario (login → chatbots → dashboard)

**Files:**
- Create: `k6/auth-read.js`

**Step 1: Create `k6/auth-read.js`**

This scenario logs in once in `setup()`, then each VU uses the token to hit chatbots + dashboard in a loop.

```javascript
// k6/auth-read.js
// Authenticated read scenario: list chatbots + dashboard.
// 10 VUs, 30s. Thresholds: p95 < 500ms, errors < 1%.
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

export const options = {
  vus: 10,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<500"],
    errors: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const EMAIL = __ENV.EMAIL || "test@pulse.dev";
const PASSWORD = __ENV.PASSWORD || "test";
const WS_ID = __ENV.WS_ID || "350863e7-3dc8-430e-bc23-fd41d4499d7b";

// setup() runs once before VUs start. Return value is passed to default() as `data`.
export function setup() {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } }
  );
  if (res.status !== 200) {
    throw new Error(`Login failed: ${res.status} ${res.body}`);
  }
  const body = JSON.parse(res.body);
  return { token: body.tokens.access_token };
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${data.token}`,
    "Content-Type": "application/json",
  };

  // Request 1: list chatbots
  const chatbotsRes = http.get(
    `${BASE_URL}/api/v1/workspaces/${WS_ID}/chatbots`,
    { headers }
  );
  const chatbotsOk = check(chatbotsRes, {
    "chatbots 200": (r) => r.status === 200,
    "chatbots is array": (r) => {
      try {
        return Array.isArray(JSON.parse(r.body));
      } catch {
        return false;
      }
    },
  });
  errorRate.add(!chatbotsOk);

  sleep(0.3);

  // Request 2: dashboard
  const dashRes = http.get(
    `${BASE_URL}/api/v1/workspaces/${WS_ID}/dashboard`,
    { headers }
  );
  const dashOk = check(dashRes, {
    "dashboard 200": (r) => r.status === 200,
  });
  errorRate.add(!dashOk);

  sleep(0.5);
}
```

**Step 2: Run the auth-read scenario**

```bash
k6 run k6/auth-read.js
```

Expected:
- `✓ chatbots 200`
- `✓ chatbots is array`
- `✓ dashboard 200`
- `http_req_duration p(95) < 500ms` ✓
- `errors rate < 1%` ✓
- Exit 0.

**Step 3: Debug if login fails**

If "Login failed: 422", check that the auth endpoint really is at `/api/v1/auth/login`:
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@pulse.dev","password":"test"}' | python3 -m json.tool
```

The response shape is `{user: {...}, tokens: {access_token, refresh_token}}` — `body.tokens.access_token` is the correct path.

**Step 4: Commit**

```bash
git add k6/auth-read.js
git commit -m "perf: add k6 authenticated read scenario (chatbots + dashboard)"
```

---

### Task 3: Widget config load test + `make perf-all`

**Files:**
- Create: `k6/widget.js`

**Step 1: Verify the widget config endpoint URL**

```bash
curl -s http://localhost:8000/api/v1/widget/a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108/config | python3 -m json.tool | head -10
```

Expected: JSON with `name`, `system_prompt`, `tone`, etc. (no auth required).

If 404, try: `curl -s http://localhost:8000/api/v1/workspaces/350863e7-3dc8-430e-bc23-fd41d4499d7b/chatbots/a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108/widget-config`

Use whichever URL returns 200 in the k6 script.

**Step 2: Create `k6/widget.js`**

The widget-config endpoint is called on every page load where the chat widget is embedded. This simulates 20 concurrent widget loads for 30s.

```javascript
// k6/widget.js
// Widget config load test: public endpoint, no auth.
// 20 VUs, 30s. Thresholds: p95 < 300ms, errors < 1%.
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

export const options = {
  vus: 20,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<300"],
    errors: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const CHATBOT_ID = __ENV.CHATBOT_ID || "a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108";

export default function () {
  const res = http.get(
    `${BASE_URL}/api/v1/widget/${CHATBOT_ID}/config`
  );
  const ok = check(res, {
    "widget config 200": (r) => r.status === 200,
    "has chatbot name": (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.name === "string" && body.name.length > 0;
      } catch {
        return false;
      }
    },
  });
  errorRate.add(!ok);
  sleep(1);
}
```

**Step 3: Run the widget scenario**

```bash
k6 run k6/widget.js
```

Expected:
- `✓ widget config 200`
- `✓ has chatbot name`
- `http_req_duration p(95) < 300ms` ✓
- `errors rate < 1%` ✓
- Exit 0.

**Step 4: Run the full suite via `make perf-all`**

```bash
make perf-all
```

Expected: all three scenarios run sequentially, all exit 0.

**Step 5: Add `.gitignore` entry for k6 summary files**

k6 produces `summary.json` and `results.html` if `--out` is used. Add to root `.gitignore` (or create one if absent):

```bash
echo "k6-results/" >> .gitignore
```

**Step 6: Commit**

```bash
git add k6/widget.js .gitignore
git commit -m "perf: add k6 widget config load test + perf-all gate"
```

**Step 7: Print final Phase 8 summary**

```
Phase 8 complete.
k6 scenarios: smoke (5 VUs/20s), auth-read (10 VUs/30s), widget (20 VUs/30s)
Thresholds: p95<200ms (health), p95<500ms (auth reads), p95<300ms (widget)
Gate: make perf-all exits 0
```
