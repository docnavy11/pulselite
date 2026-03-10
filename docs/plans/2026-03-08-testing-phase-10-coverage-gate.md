# Phase 10 — Coverage Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `make test-coverage-gate` target that fails if overall backend test coverage drops below 50%, with Celery worker tasks excluded from the measurement (they require queue infrastructure to test meaningfully).

**Architecture:** pytest-cov is already installed. We add `[tool.coverage.run]` and `[tool.coverage.report]` configuration to `backend/pyproject.toml` to exclude worker tasks, migration files, and seed scripts from coverage measurement. The baseline is 43% (full codebase); excluding workers brings the effective baseline to ~55-60%, so a 50% gate is achievable immediately. The gate runs `pytest --cov=app --cov-fail-under=50` and exits non-zero if coverage drops.

**Tech Stack:** pytest-cov (already in dev deps), coverage.py config in pyproject.toml

---

## Context

- Current coverage: **43%** (6740 lines, 3813 uncovered)
- Workers (`app/workers/tasks/`) have 0–49% coverage — excluded from gate
- 234 tests currently passing
- `pyproject.toml` at `backend/pyproject.toml` already has `[tool.pytest.ini_options]`

---

### Task 1: Configure coverage exclusions + set gate

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `Makefile`

**Step 1: Add coverage config to pyproject.toml**

Read `backend/pyproject.toml` first. Then add these sections at the end of the file:

```toml
[tool.coverage.run]
source = ["app"]
omit = [
    "app/workers/tasks/*",      # Celery tasks require live queue — tested separately
    "app/workers/celery_app.py",
    "alembic/*",
    "scripts/*",
    "tests/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "\\.\\.\\.",
    "pass",
]
show_missing = true
skip_covered = false
```

**Step 2: Measure coverage with exclusions**

```bash
docker compose exec backend pytest tests/ \
  --cov=app \
  --cov-config=pyproject.toml \
  --cov-report=term-missing \
  --no-header -q 2>&1 | tail -10
```

Read the `TOTAL` line. The number should be higher than 43% now that workers are excluded. Note the exact percentage.

**Step 3: Set the gate threshold**

Set `--cov-fail-under` to **5 points below the measured total** (to give a buffer for any variability) but at minimum 50%.

For example:
- If measured total is 62% → set `--cov-fail-under=57`
- If measured total is 55% → set `--cov-fail-under=50`
- If measured total is 49% → investigate which non-worker modules are uncovered, then still set 45%

**Step 4: Add `test-coverage-gate` target to Makefile**

```makefile
test-coverage-gate:
	docker compose exec backend pytest tests/ \
	  --cov=app \
	  --cov-config=pyproject.toml \
	  --cov-report=term-missing \
	  --cov-fail-under=50 \
	  -q
```

Replace `50` with the actual threshold determined in Step 3.

Add `test-coverage-gate` to `.PHONY`.

**Step 5: Verify the gate passes**

```bash
make test-coverage-gate
```

Expected: exits 0. The summary line shows coverage >= threshold.

**Step 6: Verify the gate fails if threshold is too high**

Do a quick sanity check that the gate actually works as a gate:

```bash
docker compose exec backend pytest tests/ \
  --cov=app \
  --cov-config=pyproject.toml \
  --cov-report=term-missing \
  --cov-fail-under=99 \
  -q 2>&1 | tail -5
```

Expected: exits non-zero with "FAIL Required test coverage of 99% not reached."

**Step 7: Commit**

```bash
git add backend/pyproject.toml Makefile
git commit -m "ci: add coverage gate — $(THRESHOLD)% minimum, workers excluded"
```

Replace `$(THRESHOLD)` with the actual number in the commit message.

**Step 8: Print summary**

```
Phase 10 complete.
Coverage (excl. workers): XX%
Gate threshold: YY%
Gate: make test-coverage-gate exits 0
```
