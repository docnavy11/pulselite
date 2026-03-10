# Phase 7 — Security Static Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run Bandit + Semgrep static security scanners against the backend, fix all HIGH/CRITICAL findings, and add `make lint-security-static` as a CI-ready gate.

**Architecture:** Bandit is added to the backend Docker dev-deps so it runs inside the container (same Python env as the app). Semgrep runs via `pip install semgrep` on the host (it needs internet to pull rulesets and is too large to bake into the image). A `.bandit` config file suppresses known false positives without hiding real issues. Both tools exit non-zero on HIGH/CRITICAL findings so they can gate CI.

**Tech Stack:** Bandit 1.8+, Semgrep 1.x, uv pip, pyproject.toml dev extras, Makefile

---

## Context

- **Backend Python files:** 149 files under `backend/app/`
- **Package manager:** `uv pip install --system -e ".[dev]"` inside Docker (defined in `backend/pyproject.toml`)
- **Dev deps section:** `[project.optional-dependencies] dev = [...]`
- **Dockerfile:** `backend/Dockerfile` — rebuild needed after adding deps
- **Existing `make test-security`**: runs `pytest tests/security/` (runtime tests). We are adding *static* analysis alongside.
- **No subprocess/eval/shell=True** found in a pre-scan — likely few HIGH findings

---

### Task 1: Add Bandit, rebuild container, run first scan, fix findings

**Files:**
- Modify: `backend/pyproject.toml` (add bandit to dev extras)
- Create: `backend/.bandit` (suppress false positives)
- Modify: possibly files in `backend/app/` if findings need fixing

**Step 1: Add bandit to dev deps**

In `backend/pyproject.toml`, add `"bandit[toml]>=1.8.0"` to the `dev` list:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "pytest-mock>=3.14.0",
    "pytest-xdist>=3.6.0",
    "faker>=33.0.0",
    "ruff>=0.8.0",
    "anyio[trio]>=4.0.0",
    "bandit[toml]>=1.8.0",
]
```

**Step 2: Rebuild the backend container**

```bash
docker compose build backend
docker compose up -d backend
```

Expected: build completes, container restarts.

**Step 3: Run bandit and capture output**

```bash
docker compose exec backend bandit -r app/ -f text -o /tmp/bandit-report.txt || true
docker compose exec backend cat /tmp/bandit-report.txt
```

Read the output carefully. Triage each finding:
- **HIGH severity** → must fix
- **MEDIUM severity** → fix if not a false positive
- **LOW severity** → suppress in `.bandit` config if not actionable

**Step 4: Create `.bandit` config to suppress false positives**

Common suppressions for this stack:
- `B105` (hardcoded password strings) — fires on test fixtures and config field names like `"password"` strings — suppress if not actual hardcoded credentials
- `B603` / `B607` — subprocess without shell — only if no subprocess used
- `B101` (assert used for security) — suppress for test files only

Create `backend/.bandit`:

```ini
[bandit]
exclude_dirs = ["tests", "scripts", "alembic"]
skips = []
```

Adjust `skips` based on actual false positives found in Step 3.

**Step 5: Fix HIGH/CRITICAL findings**

Common real findings to fix:

**(a) SSL verification disabled in httpx calls**
If any `httpx.get(url, verify=False)`, change to `verify=True` (default) or use a proper CA bundle.

**(b) Weak random used for security tokens**
If `random.choice` / `random.randint` used anywhere for token generation, replace with `secrets.token_urlsafe()`.

**(c) yaml.load without Loader**
If any `yaml.load(data)`, replace with `yaml.safe_load(data)`.

**(d) Hardcoded credentials**
If any actual hardcoded secrets found, move to environment variables via `app/config.py` Settings.

After fixes, re-run to confirm clean:
```bash
docker compose exec backend bandit -r app/ --configfile .bandit -ll
```
Expected: exit code 0 (no HIGH/CRITICAL issues remain).

**Step 6: Commit**

```bash
cd backend
git add pyproject.toml .bandit
git add app/  # any fixed files
git commit -m "security: add bandit static analysis, fix HIGH findings"
```

---

### Task 2: Run Semgrep, review findings, fix issues

**Files:**
- Modify: possibly files in `backend/app/` if findings need fixing
- Create: `backend/.semgrepignore`

**Step 1: Install semgrep on the host**

```bash
pip install semgrep
# or: pipx install semgrep
semgrep --version
```

Expected: prints version like `1.x.x`.

**Step 2: Run semgrep with Python + OWASP Top 10 rulesets**

From the repo root:

```bash
semgrep scan \
  --config=p/python \
  --config=p/owasp-top-ten \
  --config=p/secrets \
  backend/app/ \
  --output semgrep-report.txt \
  --text \
  || true

cat semgrep-report.txt
```

Expected: report listing findings by rule ID and severity.

**Step 3: Create `.semgrepignore` to exclude non-application paths**

Create `backend/.semgrepignore`:

```
tests/
scripts/
alembic/
__pycache__/
*.pyc
```

**Step 4: Triage findings**

For each finding:
- **ERROR severity** → must fix
- **WARNING severity** → fix if genuine, add `# nosemgrep: rule-id` inline comment with justification if false positive
- **INFO severity** → skip (informational only)

Common genuine findings to look for:
- SQL injection via f-string in raw queries (use SQLAlchemy params instead)
- JWT `none` algorithm accepted (check `python-jose` decode call — must pass `algorithms=["HS256"]`)
- Insecure deserialization
- Path traversal in file operations
- SSRF in URL-fetching code (web search, sitemap fetcher, OAuth discovery)

**Step 5: Fix genuine findings**

**(a) JWT algorithm pinning** — check `backend/app/utils/security.py`:
```python
# BAD: accepts any algorithm
jwt.decode(token, SECRET)

# GOOD: pin algorithm
jwt.decode(token, SECRET, algorithms=["HS256"])
```

**(b) SSRF in OAuth discovery** — `backend/app/api/v1/sso.py` fetches discovery URLs from user input.
Add a domain allowlist check or at minimum validate the URL scheme is `https://`:
```python
from urllib.parse import urlparse
parsed = urlparse(discovery_url)
if parsed.scheme != "https":
    raise HTTPException(400, "Discovery URL must use HTTPS")
```

**(c) SSRF in web search / sitemap** — verify user-supplied URLs are validated before httpx fetch.

**Step 6: Re-run semgrep to confirm clean**

```bash
semgrep scan \
  --config=p/python \
  --config=p/owasp-top-ten \
  --config=p/secrets \
  backend/app/ \
  --error
```

Expected: exit code 0 (no ERROR-level findings).

**Step 7: Commit**

```bash
git add backend/.semgrepignore backend/app/  # fixed files
git add semgrep-report.txt  # keep as artifact (add to .gitignore if preferred)
git commit -m "security: run semgrep OWASP scan, fix findings"
```

---

### Task 3: Add Makefile targets + document baseline

**Files:**
- Modify: `Makefile`

**Step 1: Add security static analysis targets to Makefile**

Read the current `Makefile` (it already has `test-security` for pytest). Add after the existing `test-e2e-headed` target:

```makefile
# ── Security Static Analysis ──────────────────────────────────────────────────

lint-bandit:
	docker compose exec backend bandit -r app/ --configfile .bandit -ll

lint-semgrep:
	cd backend && semgrep scan \
	  --config=p/python \
	  --config=p/owasp-top-ten \
	  --config=p/secrets \
	  app/ \
	  --error

lint-security-static: lint-bandit lint-semgrep
```

Also add the new targets to the `.PHONY` line:

```makefile
.PHONY: up down build migrate seed test test-unit test-integration test-isolation test-security test-all test-fast lint test-frontend test-frontend-coverage test-e2e test-e2e-headed lint-bandit lint-semgrep lint-security-static
```

**Step 2: Verify both targets work**

```bash
make lint-bandit
```
Expected: exit 0, prints "No issues identified." or only LOW findings.

```bash
make lint-semgrep
```
Expected: exit 0.

**Step 3: Commit**

```bash
git add Makefile
git commit -m "ci: add lint-bandit, lint-semgrep, lint-security-static Makefile targets"
```

**Step 4: Print final summary**

After committing, print:
```
Phase 7 complete.
Bandit: X findings fixed, Y false positives suppressed
Semgrep: X findings fixed, Y false positives annotated
Gate: make lint-security-static exits 0
```
