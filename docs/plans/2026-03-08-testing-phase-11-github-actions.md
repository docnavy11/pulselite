# Phase 11 — GitHub Actions CI/CD Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a GitHub Actions CI workflow that runs the full test suite (lint → security → backend tests → coverage gate → frontend unit → E2E → schemathesis → k6 smoke) on every push and pull request to `main`.

**Architecture:** A single workflow file (`.github/workflows/ci.yml`) using `ubuntu-latest`. All backend services start via `docker compose up -d`. Tests run via `docker compose exec` (mirrors dev environment exactly). Frontend tests run natively (Node.js installed by GH Actions). Playwright E2E runs against the live frontend container. k6 installs from the official apt repo. The workflow is split into jobs: `lint`, `backend-tests`, `frontend-tests`, `e2e`, and `schema-perf` — running sequentially with `needs:` to fail fast.

**Tech Stack:** GitHub Actions, Docker Compose (included in ubuntu-latest), k6 (apt), schemathesis (pip), Node.js 20, Playwright

---

## Context

- Repo root: `/Users/yvanveldeman/dev/pulse`
- No existing `.github/workflows/` directory
- All test commands are already defined in `Makefile`
- Backend: Docker Compose (postgres, redis, backend, celery_worker, celery_beat, frontend)
- Frontend: Next.js 15, runs in Docker on port 3001
- E2E: Playwright, needs a running frontend at `http://localhost:3001`
- Secrets needed in GH repo settings: none required for dev/CI (all tests use dev seeds)
- `make migrate && make seed` required before tests

---

### Task 1: Create `.github/workflows/ci.yml` — lint + backend tests

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: Create the workflows directory**

```bash
mkdir -p /Users/yvanveldeman/dev/pulse/.github/workflows
```

**Step 2: Create `.github/workflows/ci.yml`**

Create the file with this content:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  COMPOSE_FILE: docker-compose.yml

jobs:
  # ── Job 1: Lint ────────────────────────────────────────────────────────────
  lint:
    name: Lint & Static Analysis
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start services
        run: docker compose up -d backend
        working-directory: .

      - name: Wait for backend
        run: |
          for i in {1..30}; do
            docker compose exec -T backend python -c "print('ok')" 2>/dev/null && break
            sleep 2
          done

      - name: Ruff lint
        run: docker compose exec -T backend ruff check app/

      - name: Ruff format check
        run: docker compose exec -T backend ruff format --check app/

      - name: Bandit
        run: docker compose exec -T backend bandit -r app/ --configfile .bandit -ll

      - name: Semgrep
        run: |
          pip install semgrep
          semgrep scan \
            --config=p/python \
            --config=p/owasp-top-ten \
            --config=p/secrets \
            backend/app/ \
            --error

  # ── Job 2: Backend Tests ───────────────────────────────────────────────────
  backend-tests:
    name: Backend Tests + Coverage
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - name: Start all services
        run: |
          docker compose up -d
          sleep 10

      - name: Wait for postgres
        run: |
          for i in {1..30}; do
            docker compose exec -T postgres pg_isready -U pulse && break
            sleep 2
          done

      - name: Run migrations
        run: docker compose exec -T backend bash -c "PYTHONPATH=/app alembic upgrade head"

      - name: Seed dev data
        run: docker compose exec -T backend python scripts/seed.py

      - name: Run backend tests
        run: docker compose exec -T backend pytest tests/ -v --tb=short

      - name: Coverage gate
        run: |
          docker compose exec -T backend pytest tests/ \
            --cov=app \
            --cov-config=pyproject.toml \
            --cov-report=term-missing \
            --cov-fail-under=50 \
            -q

  # ── Job 3: Frontend Tests ─────────────────────────────────────────────────
  frontend-tests:
    name: Frontend Unit Tests
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci
        working-directory: frontend

      - name: Run Vitest
        run: npx vitest run
        working-directory: frontend

  # ── Job 4: E2E Tests ───────────────────────────────────────────────────────
  e2e:
    name: E2E Tests (Playwright)
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]
    steps:
      - uses: actions/checkout@v4

      - name: Start all services
        run: |
          docker compose up -d
          sleep 15

      - name: Wait for postgres
        run: |
          for i in {1..30}; do
            docker compose exec -T postgres pg_isready -U pulse && break
            sleep 2
          done

      - name: Run migrations + seed
        run: |
          docker compose exec -T backend bash -c "PYTHONPATH=/app alembic upgrade head"
          docker compose exec -T backend python scripts/seed.py

      - name: Wait for frontend
        run: |
          for i in {1..30}; do
            curl -sf http://localhost:3001 > /dev/null 2>&1 && break
            sleep 3
          done

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci
        working-directory: frontend

      - name: Install Playwright browsers
        run: npx playwright install --with-deps chromium
        working-directory: frontend

      - name: Run E2E tests
        run: npx playwright test
        working-directory: frontend

      - name: Upload Playwright report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend/playwright-report/

  # ── Job 5: Schema + Perf ──────────────────────────────────────────────────
  schema-perf:
    name: Schemathesis + k6 Smoke
    runs-on: ubuntu-latest
    needs: backend-tests
    steps:
      - uses: actions/checkout@v4

      - name: Start all services
        run: |
          docker compose up -d
          sleep 10

      - name: Wait for postgres + migrate + seed
        run: |
          for i in {1..30}; do
            docker compose exec -T postgres pg_isready -U pulse && break
            sleep 2
          done
          docker compose exec -T backend bash -c "PYTHONPATH=/app alembic upgrade head"
          docker compose exec -T backend python scripts/seed.py

      - name: Install schemathesis
        run: pip install schemathesis

      - name: Schemathesis — public endpoints
        run: |
          st run http://localhost:8000/openapi.json \
            --checks all \
            --exclude-path-regex "/auth/google|/auth/sso|/oauth|/shopify|/whatsapp|/messenger|/instagram|/slack" \
            --exclude-path-regex "/public/chat|/share/|/chat$$|/chat/completions" \
            --hypothesis-max-examples=10 \
            --validate-schema=false

      - name: Install k6
        run: |
          sudo gpg -k
          sudo gpg --no-default-keyring \
            --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
            --keyserver hkp://keyserver.ubuntu.com:80 \
            --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
            | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6

      - name: k6 smoke test
        run: k6 run k6/smoke.js
```

**Step 3: Create a minimal `.env.example` for CI if needed**

Check if `docker-compose.yml` uses env vars that need to be set for CI. Read the `docker-compose.yml` and `.env.example` files:

```bash
head -30 /Users/yvanveldeman/dev/pulse/docker-compose.yml
cat /Users/yvanveldeman/dev/pulse/.env.example 2>/dev/null | head -20
```

If `docker-compose.yml` references an `.env` file, create a CI-appropriate `.env` file in the workflow using `env:` block or by echoing a minimal `.env` in a setup step.

**Step 4: Validate the YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "Valid YAML"
```

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions CI pipeline (lint, backend, frontend, e2e, schema, k6)"
```

---

### Task 2: Add `.env` handling for CI + validate workflow

**Files:**
- Modify: `.github/workflows/ci.yml` (add env setup step if needed)
- Modify: `.env.example` (document CI-required vars)

**Step 1: Check what env vars docker-compose.yml needs**

Read `docker-compose.yml` and `.env.example` to identify required secrets:

```bash
cat /Users/yvanveldeman/dev/pulse/.env.example
```

Look for:
- `SECRET_KEY` — must be set (any 32+ char string works for CI)
- `DATABASE_URL` — set to the docker-compose postgres
- `REDIS_URL` — set to the docker-compose redis
- Any third-party API keys (OpenAI, etc.) — set to `test` or leave blank

**Step 2: Add CI env setup step to the workflow**

If any env vars are missing, add an early step in each job that needs them:

```yaml
      - name: Create .env for CI
        run: |
          cat > .env << 'EOF'
          SECRET_KEY=ci-test-secret-key-32-chars-minimum
          OPENAI_API_KEY=test
          ANTHROPIC_API_KEY=test
          EOF
```

OR if `.env.example` already has safe defaults for all CI-required vars:
```yaml
      - name: Create .env for CI
        run: cp .env.example .env
```

**Step 3: Re-validate the workflow file**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "Valid YAML"
```

**Step 4: Check coverage threshold matches Phase 10**

Read the Makefile `test-coverage-gate` target to get the actual `--cov-fail-under` value used. Update the `ci.yml` `backend-tests` coverage gate step to use the same value.

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml .env.example
git commit -m "ci: add env setup for CI, align coverage threshold with Makefile"
```

**Step 6: Print final summary**

```
Phase 11 complete.
CI jobs: lint | backend-tests | frontend-tests | e2e | schema-perf
Triggers: push/PR to main
Coverage gate: matches make test-coverage-gate
Gate: valid YAML, all jobs structured correctly
```
