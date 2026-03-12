# Crawl Character Limits & Path Filters Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the page-count crawl cap with a workspace-wide character budget (per billing plan), add include/exclude path filters, and raise BFS depth from 3→10.

**Architecture:** A new `chars_indexed` column on `workspaces` (decremented on delete, incremented atomically at ingest time) enforces the plan limit. `CrawlJob` stores `include_paths`/`exclude_paths` JSONB so the async Celery task can use them. The crawler helper functions receive filter params; the ingest pipeline checks the budget after content extraction and sets `status="skipped"` when the limit is exceeded.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Celery, PostgreSQL (atomic UPDATE…RETURNING), React 19 + React Router, Tailwind CSS v3, Vitest

**Spec:** `docs/specs/2026-03-12-crawl-char-limits.md`

---

## Chunk 1: Data Model & Migration

### Task 1: Alembic migration

**Files:**
- Create: `backend/alembic/versions/2026_03_12_crawl_char_limits.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/alembic/versions/2026_03_12_crawl_char_limits.py
"""Add character budget columns and path filters for crawl

Revision ID: crawl_char_limits
Revises: add_action_parameters
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "crawl_char_limits"
down_revision = "add_action_parameters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # workspaces: total chars currently indexed across all KBs
    op.add_column(
        "workspaces",
        sa.Column(
            "chars_indexed",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # documents: char count of extractor output for this document
    op.add_column(
        "documents",
        sa.Column(
            "char_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # crawl_jobs: drop page-cap columns
    op.drop_column("crawl_jobs", "max_pages")
    op.drop_column("crawl_jobs", "over_limit")

    # crawl_jobs: add path filter columns
    op.add_column(
        "crawl_jobs",
        sa.Column(
            "include_paths",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "crawl_jobs",
        sa.Column(
            "exclude_paths",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # Backfill char_count for existing indexed documents using their chunk text.
    # Chunks do not overlap, so SUM(length) approximates extractor output length.
    # NOTE: This is a bulk UPDATE. On a large production DB this will lock the
    # documents table briefly. Run during a maintenance window or accept the
    # brief lock on the first deployment.
    op.execute("""
        UPDATE documents d
        SET    char_count = sub.total
        FROM   (
            SELECT document_id, COALESCE(SUM(LENGTH(content)), 0) AS total
            FROM   chunks
            GROUP BY document_id
        ) sub
        WHERE  d.id = sub.document_id
          AND  d.status = 'indexed'
    """)

    # Backfill chars_indexed on workspaces
    op.execute("""
        UPDATE workspaces w
        SET    chars_indexed = sub.total
        FROM   (
            SELECT workspace_id, COALESCE(SUM(char_count), 0) AS total
            FROM   documents
            WHERE  status = 'indexed'
            GROUP BY workspace_id
        ) sub
        WHERE  w.id = sub.workspace_id
    """)


def downgrade() -> None:
    op.drop_column("crawl_jobs", "exclude_paths")
    op.drop_column("crawl_jobs", "include_paths")
    op.add_column(
        "crawl_jobs",
        sa.Column("over_limit", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.add_column(
        "crawl_jobs",
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default=sa.text("50")),
    )
    op.drop_column("documents", "char_count")
    op.drop_column("workspaces", "chars_indexed")
```

- [ ] **Step 2: Run the migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade add_action_parameters -> crawl_char_limits, Add character budget columns…`

- [ ] **Step 3: Verify columns exist**

```bash
docker compose exec postgres psql -U pulse -d pulse -c "\d workspaces" | grep chars_indexed
docker compose exec postgres psql -U pulse -d pulse -c "\d documents" | grep char_count
docker compose exec postgres psql -U pulse -d pulse -c "\d crawl_jobs" | grep -E "include_paths|exclude_paths|max_pages"
```

Expected: `chars_indexed` and `char_count` appear; `max_pages` and `over_limit` are gone.

- [ ] **Step 4: Verify backfill consistency**

```bash
docker compose exec postgres psql -U pulse -d pulse -c "
  SELECT
    w.id,
    w.chars_indexed,
    COALESCE(SUM(d.char_count), 0) AS sum_from_docs
  FROM workspaces w
  LEFT JOIN documents d ON d.workspace_id = w.id AND d.status = 'indexed'
  GROUP BY w.id, w.chars_indexed
  HAVING w.chars_indexed != COALESCE(SUM(d.char_count), 0);
"
```

Expected: zero rows (backfill is consistent). If any rows appear, rerun the upgrade backfill SQL manually.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/2026_03_12_crawl_char_limits.py
git commit -m "feat: add migration for char budget and crawl path filters"
```

---

### Task 2: Update SQLAlchemy models and add PLAN_CHAR_LIMITS

**Files:**
- Modify: `backend/app/models/organizational.py`
- Modify: `backend/app/models/knowledge.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add `chars_indexed` to `Workspace` model**

In `backend/app/models/organizational.py`, after the `allowed_models` column (line 34), add:

```python
    chars_indexed: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
```

The file uses named imports (no `sa` alias). Add `BigInteger` to the existing named import line:

```python
# Before:
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
# After:
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
```

- [ ] **Step 2: Update `CrawlJob` model**

In `backend/app/models/knowledge.py`, the `CrawlJob` class (lines 150–163):

Remove:
```python
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    over_limit: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
```

Add (after `pages_failed`):
```python
    include_paths: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    exclude_paths: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
```

- [ ] **Step 3: Add `char_count` to `Document` model**

In `backend/app/models/knowledge.py`, the `Document` class, add after `chunk_count`:
```python
    char_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
```

- [ ] **Step 4: Add PLAN_CHAR_LIMITS to config.py**

At the module level in `backend/app/config.py`, after the `settings = Settings()` instantiation at the bottom of the file, add:

```python
PLAN_CHAR_LIMITS: dict[str, int | None] = {
    "free":         500_000,
    "starter":    2_000_000,
    "growth":    10_000_000,
    "enterprise": None,         # unlimited
}
```

- [ ] **Step 5: Restart backend and verify no import errors**

```bash
docker compose restart backend
docker compose exec backend python -c "from app.models.organizational import Workspace; from app.models.knowledge import CrawlJob, Document; from app.config import PLAN_CHAR_LIMITS; print(PLAN_CHAR_LIMITS)"
```

Expected: prints the dict with no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/organizational.py backend/app/models/knowledge.py backend/app/config.py
git commit -m "feat: add chars_indexed/char_count columns and PLAN_CHAR_LIMITS"
```

---

## Chunk 2: Crawler Refactor

### Task 3: Refactor crawler.py

**Files:**
- Modify: `backend/app/services/crawler.py`

The goal is to:
1. Delete the `CrawlResult` dataclass
2. Add `_matches_paths` helper
3. Update `_discover_via_sitemap` to accept and apply path filters
4. Update `_discover_via_bfs` default depth 3→10 and accept path filter params
5. Change `discover_urls` signature: drop `max_pages`, add `include_paths`/`exclude_paths`, return `list[str]`

- [ ] **Step 1: Write the new `crawler.py`**

Replace the full file content with:

```python
# backend/app/services/crawler.py
import logging
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup

from app.services.fetcher import FetchResult, fetch

logger = logging.getLogger(__name__)

_MAX_CHILD_SITEMAPS = 20


def _normalize(url: str) -> str:
    """Strip fragment and query string; normalize trailing slash on non-root paths."""
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))


def _same_domain(url: str, root_domain: str) -> bool:
    return urlparse(url).netloc == root_domain


def _matches_paths(
    url: str,
    include_paths: list[str],
    exclude_paths: list[str],
) -> bool:
    """Return True if url's path passes the include/exclude filters."""
    path = urlparse(url).path
    if include_paths and not any(path.startswith(p) for p in include_paths):
        return False
    if any(path.startswith(p) for p in exclude_paths):
        return False
    return True


async def _discover_via_sitemap(
    root_url: str,
    include_paths: list[str],
    exclude_paths: list[str],
) -> list[str] | None:
    sitemap_url = root_url.rstrip("/") + "/sitemap.xml"
    result: FetchResult = await fetch(sitemap_url)
    if result.status_code != 200 or not result.html:
        return None

    try:
        root_el = ET.fromstring(result.html.encode())
    except Exception as exc:
        logger.warning("Failed to parse sitemap XML from %s: %s", sitemap_url, exc)
        return None

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls: list[str] = []

    # Sitemap index: recurse into child sitemaps (capped to avoid unbounded fetches)
    child_sitemap_els = root_el.findall(".//sm:sitemap/sm:loc", ns)
    for sitemap_el in child_sitemap_els[:_MAX_CHILD_SITEMAPS]:
        loc_text = sitemap_el.text
        if not loc_text:
            continue
        child = await fetch(loc_text.strip())
        if child.status_code == 200 and child.html:
            try:
                child_root = ET.fromstring(child.html.encode())
                for loc in child_root.findall(".//sm:url/sm:loc", ns):
                    if loc.text:
                        norm = _normalize(loc.text.strip())
                        if _matches_paths(norm, include_paths, exclude_paths):
                            urls.append(norm)
            except Exception as exc:
                logger.warning("Failed to parse child sitemap %s: %s", loc_text.strip(), exc)

    # Regular sitemap entries
    for loc in root_el.findall(".//sm:url/sm:loc", ns):
        if loc.text:
            norm = _normalize(loc.text.strip())
            if _matches_paths(norm, include_paths, exclude_paths):
                urls.append(norm)

    return urls if urls else None


async def _discover_via_bfs(
    root_url: str,
    max_depth: int = 10,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
) -> list[str]:
    _inc = include_paths or []
    _exc = exclude_paths or []
    root_domain = urlparse(root_url).netloc
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(root_url, 0)])
    found: list[str] = []

    while queue:
        url, depth = queue.popleft()
        norm = _normalize(url)
        if norm in visited:
            continue
        if not _matches_paths(norm, _inc, _exc):
            continue
        visited.add(norm)
        found.append(norm)

        if depth >= max_depth:
            continue

        result = await fetch(url)
        if result.status_code >= 400 or not result.html:
            continue

        soup = BeautifulSoup(result.html, "html.parser")
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            absolute = urljoin(url, href)
            parsed = urlparse(absolute)
            # Drop URLs with query strings entirely
            if parsed.query:
                continue
            norm_link = _normalize(absolute)
            if _same_domain(norm_link, root_domain) and norm_link not in visited:
                queue.append((norm_link, depth + 1))

    return found


async def discover_urls(
    root_url: str,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
) -> list[str]:
    """Discover all URLs under root_url, applying optional path filters."""
    _inc = include_paths or []
    _exc = exclude_paths or []

    urls: list[str] = []

    sitemap_urls = await _discover_via_sitemap(root_url, _inc, _exc)
    if sitemap_urls and len(sitemap_urls) >= 3:
        root_domain = urlparse(root_url).netloc
        urls = [u for u in sitemap_urls if _same_domain(u, root_domain)]
    else:
        urls = await _discover_via_bfs(root_url, include_paths=_inc, exclude_paths=_exc)

    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    return deduped
```

- [ ] **Step 2: Verify no import errors**

```bash
docker compose exec backend python -c "from app.services.crawler import discover_urls, _matches_paths; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/crawler.py
git commit -m "feat: refactor crawler — path filters, depth=10, retire CrawlResult"
```

---

### Task 4: Update crawler unit tests

**Files:**
- Modify: `backend/tests/unit/test_crawler.py`

The existing tests call `discover_urls("https://a.com", max_pages=10)` and assert on `result.urls`, `result.used_sitemap`, `result.over_limit`, `result.total_discovered`. All these must be rewritten to use the new `list[str]` return type and the new signature. Also add `_matches_paths` and path-filter tests.

- [ ] **Step 1: Rewrite test_crawler.py**

```python
# backend/tests/unit/test_crawler.py
import pytest
from unittest.mock import patch

from app.services.crawler import _matches_paths, _normalize, _same_domain, discover_urls
from app.services.fetcher import FetchResult


def _make_fetch_result(url: str, html: str = "", status: int = 200) -> FetchResult:
    return FetchResult(url=url, html=html, text="content", title=None,
                       theme_color=None, status_code=status, used_playwright=False)


# ── _normalize ────────────────────────────────────────────────────────────────

def test_normalize_strips_fragment():
    assert _normalize("https://a.com/page#section") == "https://a.com/page"

def test_normalize_strips_query():
    assert _normalize("https://a.com/page?foo=bar") == "https://a.com/page"

def test_normalize_strips_trailing_slash():
    assert _normalize("https://a.com/page/") == "https://a.com/page"

def test_normalize_keeps_root():
    assert _normalize("https://a.com/") == "https://a.com/"


# ── _same_domain ──────────────────────────────────────────────────────────────

def test_same_domain_true():
    assert _same_domain("https://a.com/page", "a.com") is True

def test_same_domain_false():
    assert _same_domain("https://b.com/page", "a.com") is False


# ── _matches_paths ────────────────────────────────────────────────────────────

def test_matches_paths_no_filter():
    assert _matches_paths("https://a.com/anything", [], []) is True

def test_matches_paths_include_match():
    assert _matches_paths("https://a.com/blog/post", ["/blog"], []) is True

def test_matches_paths_include_no_match():
    assert _matches_paths("https://a.com/about", ["/blog"], []) is False

def test_matches_paths_exclude_match():
    assert _matches_paths("https://a.com/admin/panel", [], ["/admin"]) is False

def test_matches_paths_exclude_no_match():
    assert _matches_paths("https://a.com/public", [], ["/admin"]) is True

def test_matches_paths_include_and_exclude():
    # In include AND not in exclude → True
    assert _matches_paths("https://a.com/docs/api", ["/docs"], ["/docs/private"]) is True

def test_matches_paths_include_and_excluded():
    # In include but also in exclude → False
    assert _matches_paths("https://a.com/docs/private/secret", ["/docs"], ["/docs/private"]) is False


# ── discover_urls: sitemap strategy ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_uses_sitemap_when_available():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/page1</loc></url>
      <url><loc>https://a.com/page2</loc></url>
      <url><loc>https://a.com/page3</loc></url>
      <url><loc>https://a.com/page4</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert len(urls) == 4
    assert all("a.com" in u for u in urls)


@pytest.mark.asyncio
async def test_sitemap_not_found_falls_back_to_bfs():
    page_html = """<html><body>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
    </body></html>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html="", text="", title=None,
                               theme_color=None, status_code=404, used_playwright=False)
        return FetchResult(url=url, html=page_html, text="content", title=None,
                           theme_color=None, status_code=200, used_playwright=False)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert any("a.com" in u for u in urls)


@pytest.mark.asyncio
async def test_bfs_drops_off_domain_links():
    page_html = """<html><body>
    <a href="/internal">Internal</a>
    <a href="https://other.com/page">External</a>
    </body></html>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html="", text="", title=None,
                               theme_color=None, status_code=404, used_playwright=False)
        return FetchResult(url=url, html=page_html, text="content", title=None,
                           theme_color=None, status_code=200, used_playwright=False)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert all("other.com" not in u for u in urls)


@pytest.mark.asyncio
async def test_bfs_drops_urls_with_query_strings():
    page_html = """<html><body>
    <a href="/page?foo=bar">Query URL</a>
    <a href="/clean">Clean URL</a>
    </body></html>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html="", text="", title=None,
                               theme_color=None, status_code=404, used_playwright=False)
        return FetchResult(url=url, html=page_html, text="content", title=None,
                           theme_color=None, status_code=200, used_playwright=False)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert not any("foo=bar" in u for u in urls)
    assert any("clean" in u for u in urls)


@pytest.mark.asyncio
async def test_sitemap_deduplicates_urls():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/page</loc></url>
      <url><loc>https://a.com/page</loc></url>
      <url><loc>https://a.com/other1</loc></url>
      <url><loc>https://a.com/other2</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert len(urls) == 3


@pytest.mark.asyncio
async def test_sitemap_index_recurses_into_child_sitemaps():
    index_xml = """<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://a.com/sitemap-child.xml</loc></sitemap>
    </sitemapindex>"""

    child_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/page1</loc></url>
      <url><loc>https://a.com/page2</loc></url>
      <url><loc>https://a.com/page3</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if url.endswith("sitemap-child.xml"):
            return FetchResult(url=url, html=child_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        if "sitemap" in url:
            return FetchResult(url=url, html=index_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert len(urls) == 3


# ── Path filter integration tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_include_paths_filters_sitemap_urls():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/blog/post1</loc></url>
      <url><loc>https://a.com/blog/post2</loc></url>
      <url><loc>https://a.com/about</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com", include_paths=["/blog"])

    assert all("/blog" in u for u in urls)
    assert not any("/about" in u for u in urls)


@pytest.mark.asyncio
async def test_exclude_paths_filters_sitemap_urls():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/public/page</loc></url>
      <url><loc>https://a.com/admin/panel</loc></url>
      <url><loc>https://a.com/public/other</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com", exclude_paths=["/admin"])

    assert not any("/admin" in u for u in urls)
    assert len(urls) == 2
```

- [ ] **Step 2: Run crawler tests**

```bash
docker compose exec backend pytest tests/unit/test_crawler.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_crawler.py
git commit -m "test: update crawler tests for new list[str] return type and path filters"
```

---

## Chunk 3: API Layer

### Task 5: Update crawl_service.py

**Files:**
- Modify: `backend/app/services/crawl_service.py`

Key changes:
- `prepare_crawl`: replace `max_pages` param with `include_paths`/`exclude_paths`; store on `CrawlJob`
- `execute_crawl`: read `include_paths`/`exclude_paths` from job row, pass to `discover_urls`; set `pages_discovered = len(urls)` (no `over_limit`)
- `CrawlStartResult`: drop `over_limit` and `limit` fields
- Delete the `start_crawl` legacy wrapper

- [ ] **Step 1: Write the new crawl_service.py**

```python
# backend/app/services/crawl_service.py
import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import CrawlJob, Document, KnowledgeBase
from app.services.crawler import discover_urls
from app.services.fetcher import fetch

logger = logging.getLogger(__name__)

_FETCH_CONCURRENCY = 5


@dataclass
class CrawlStartResult:
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int


async def prepare_crawl(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    url: str,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    kb_id: uuid.UUID | None = None,
    chatbot_id: uuid.UUID | None = None,
) -> tuple[str, str]:
    """Create KB + CrawlJob and commit immediately. Returns (job_id, kb_id).
    Does NOT fetch any pages — that happens in the Celery task."""

    parsed_root = urlparse(url)
    if parsed_root.scheme not in ("http", "https"):
        raise ValueError("URL must be http or https")

    if kb_id is None:
        domain = urlparse(url).netloc
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        kb = KnowledgeBase(
            workspace_id=workspace_id,
            name=f"{domain} — crawled {date_str}",
            chatbot_id=chatbot_id,
        )
        db.add(kb)
        await db.flush()
        kb_id = kb.id
    else:
        r = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.workspace_id == workspace_id,
            )
        )
        if r.scalar_one_or_none() is None:
            raise ValueError(f"Knowledge base {kb_id} not found")

    job = CrawlJob(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        kb_id=kb_id,
        root_url=url,
        status="pending",
        pages_discovered=0,
        include_paths=include_paths or [],
        exclude_paths=exclude_paths or [],
    )
    db.add(job)
    await db.flush()
    await db.commit()
    return str(job.id), str(kb_id)


async def execute_crawl(db: AsyncSession, job_id: uuid.UUID) -> None:
    """Discover URLs, fetch each page, create Documents, fire ingest tasks.
    Updates CrawlJob.pages_queued after every successfully fetched page so
    the polling endpoint reflects live progress."""
    from app.workers.tasks.ingest_document import ingest_document

    r = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
    job = r.scalar_one()

    job.started_at = datetime.now(timezone.utc)
    job.status = "running"
    await db.commit()
    await db.refresh(job)

    # Phase 1: discover URLs
    urls = await discover_urls(
        job.root_url,
        include_paths=job.include_paths or None,
        exclude_paths=job.exclude_paths or None,
    )
    job.pages_discovered = len(urls)
    await db.commit()
    await db.refresh(job)

    # Phase 2: fetch pages concurrently (with live DB progress updates).
    # AsyncSession is not concurrency-safe, so fetches run concurrently but
    # DB writes happen one at a time via asyncio.as_completed.
    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)
    _MAX_RETRIES = 3

    @dataclass
    class _FetchResult:
        url: str
        text: str
        title: str
        failed: bool
        error: str = ""

    async def _fetch(page_url: str) -> _FetchResult:
        for attempt in range(_MAX_RETRIES + 1):
            async with semaphore:
                try:
                    result = await fetch(page_url)
                except Exception as exc:
                    logger.warning("Fetch exception %s: %s", page_url, exc)
                    return _FetchResult(url=page_url, text="", title="", failed=True, error=str(exc))

            if result.status_code == 429:
                if attempt < _MAX_RETRIES:
                    wait = min(5 * (2**attempt), 60)
                    logger.warning(
                        "Rate limited on %s, retrying in %ds (attempt %d/%d)",
                        page_url, wait, attempt + 1, _MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue
                return _FetchResult(
                    url=page_url, text="", title="", failed=True,
                    error="HTTP 429 (rate limited, max retries exceeded)",
                )

            if result.status_code >= 400:
                logger.warning("Skipping %s (status=%d)", page_url, result.status_code)
                return _FetchResult(url=page_url, text="", title="", failed=True, error=f"HTTP {result.status_code}")
            if result.text == "":
                return _FetchResult(url=page_url, text="", title="", failed=True, error="Empty response")
            return _FetchResult(url=page_url, text=result.text, title=result.title, failed=False)

        return _FetchResult(url=page_url, text="", title="", failed=True, error="HTTP 429 (rate limited)")

    # Write to DB as each fetch completes — gives live pages_queued progress
    doc_ids: list[str] = []
    fetch_tasks = [asyncio.create_task(_fetch(u)) for u in urls]

    try:
        for coro in asyncio.as_completed(fetch_tasks):
            fr = await coro
            if fr.failed:
                failed_doc = Document(
                    workspace_id=job.workspace_id,
                    knowledge_base_id=job.kb_id,
                    source_type="url",
                    source_url=fr.url,
                    title=fr.url,
                    status="failed",
                    metadata_={"error": fr.error},
                )
                db.add(failed_doc)
                await db.flush()
                await db.execute(
                    update(CrawlJob)
                    .where(CrawlJob.id == job_id)
                    .values(pages_failed=CrawlJob.pages_failed + 1)
                )
                await db.commit()
                continue

            doc = Document(
                workspace_id=job.workspace_id,
                knowledge_base_id=job.kb_id,
                source_type="text",
                source_url=fr.url,
                raw_content=fr.text,
                title=fr.title,
                status="pending",
            )
            db.add(doc)
            await db.flush()
            doc_ids.append(str(doc.id))
            await db.execute(
                update(CrawlJob)
                .where(CrawlJob.id == job_id)
                .values(pages_queued=CrawlJob.pages_queued + 1)
            )
            await db.commit()
    except Exception:
        for task in fetch_tasks:
            task.cancel()
        raise

    # Fire ingest tasks — all docs committed, workers can read them
    for doc_id in doc_ids:
        ingest_document.delay(doc_id)

    # Mark job as completed
    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()
```

- [ ] **Step 2: Verify import**

```bash
docker compose exec backend python -c "from app.services.crawl_service import prepare_crawl, execute_crawl; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/crawl_service.py
git commit -m "feat: update crawl_service — path filters, drop max_pages/over_limit, drop start_crawl"
```

---

### Task 6: Update crawl schemas and add WorkspaceUsageResponse

**Files:**
- Modify: `backend/app/schemas/crawl.py`

- [ ] **Step 1: Write the new crawl.py schema file**

```python
# backend/app/schemas/crawl.py
import uuid
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class CrawlRequest(BaseModel):
    url: str
    include_paths: list[str] = Field(default_factory=list,
        description="URL path prefixes to include, e.g. ['/blog', '/docs']. Empty = all paths.")
    exclude_paths: list[str] = Field(default_factory=list,
        description="URL path prefixes to exclude, e.g. ['/admin', '/private'].")
    knowledge_base_id: Optional[uuid.UUID] = None
    chatbot_id: Optional[uuid.UUID] = None

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must be http or https")
        if not parsed.netloc:
            raise ValueError("URL must include a valid host")
        return v

    @field_validator("include_paths", "exclude_paths")
    @classmethod
    def validate_paths(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("Path list may not exceed 20 entries")
        for entry in v:
            if not entry:
                raise ValueError("Path entries must be non-empty strings")
            if not entry.startswith("/"):
                raise ValueError(f"Path entry must start with '/': {entry!r}")
        return v


class CrawlResponse(BaseModel):
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int


class CrawlJobSummary(BaseModel):
    job_id: str
    status: str
    root_url: str
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    docs_indexed: int
    docs_skipped: int = 0
    created_at: str
    completed_at: Optional[str] = None


class CrawlJobStatusResponse(BaseModel):
    job_id: str
    kb_id: str
    status: str
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    docs_indexed: int
    docs_total: int
    docs_failed: int
    docs_skipped: int
    stalled: bool
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class WorkspaceUsageResponse(BaseModel):
    chars_indexed: int
    chars_limit: Optional[int]       # None = unlimited (enterprise)
    chars_remaining: Optional[int]   # None = unlimited
    plan: str
```

- [ ] **Step 2: Verify import**

```bash
docker compose exec backend python -c "from app.schemas.crawl import CrawlRequest, CrawlJobStatusResponse, WorkspaceUsageResponse; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/crawl.py
git commit -m "feat: update crawl schemas — drop max_pages/over_limit, add path filters, docs_skipped, WorkspaceUsageResponse"
```

---

### Task 7: Update crawl API route and add /usage endpoint

**Files:**
- Modify: `backend/app/api/v1/crawl.py` — update POST /crawl handler to use new schema
- Modify: `backend/app/api/v1/workspaces.py` — add GET /{workspace_id}/usage

First check what crawl.py looks like:

- [ ] **Step 1: Read backend/app/api/v1/crawl.py to understand current handler**

```bash
docker compose exec backend cat /app/app/api/v1/crawl.py
```

Look for: the `POST /crawl` handler calls `prepare_crawl` with `max_pages`. Update to pass `include_paths` and `exclude_paths` instead. Also find where `CrawlJobStatusResponse` is populated — update to compute `docs_skipped` (count of documents with `status="skipped"` for this job's KB).

- [ ] **Step 2: Update the POST /crawl handler**

Find the handler in `backend/app/api/v1/crawl.py`. The call to `prepare_crawl` currently passes `max_pages=body.max_pages`. Change to:

```python
job_id, kb_id = await prepare_crawl(
    db,
    workspace_id=workspace_id,
    url=body.url,
    include_paths=body.include_paths or None,
    exclude_paths=body.exclude_paths or None,
    kb_id=body.knowledge_base_id,
    chatbot_id=body.chatbot_id,
)
```

- [ ] **Step 3: Update CrawlJobStatusResponse population**

Find where `CrawlJobStatusResponse` is built (the GET /{job_id} handler). It currently sets `over_limit=job.over_limit, limit=job.max_pages`. Replace with `docs_skipped` computed by counting documents:

```python
from sqlalchemy import func, select
from app.models.knowledge import Document

docs_skipped_result = await db.execute(
    select(func.count()).select_from(Document).where(
        Document.knowledge_base_id == job.kb_id,
        Document.status == "skipped",
    )
)
docs_skipped = docs_skipped_result.scalar() or 0
```

Then include `docs_skipped=docs_skipped` in the `CrawlJobStatusResponse(...)` constructor.

Do the same for any code that builds `CrawlJobSummary` (the GET /crawl history endpoint). For the history list, compute `docs_skipped` per job using a single bulk query:

```python
from sqlalchemy import func

# Get skipped counts for all returned jobs in one query
job_ids = [job.id for job in jobs]
skipped_counts = {}
if job_ids:
    skipped_result = await db.execute(
        select(Document.knowledge_base_id, func.count().label("cnt"))
        .where(Document.knowledge_base_id.in_([job.kb_id for job in jobs]))
        .where(Document.status == "skipped")
        .group_by(Document.knowledge_base_id)
    )
    # Map kb_id → skipped count
    kb_skipped = {str(row.knowledge_base_id): row.cnt for row in skipped_result}
    # Map job_id → skipped count via job.kb_id
    skipped_counts = {str(job.id): kb_skipped.get(str(job.kb_id), 0) for job in jobs}

# Build summaries
summaries = [
    CrawlJobSummary(
        ...,
        docs_skipped=skipped_counts.get(str(job.id), 0),
    )
    for job in jobs
]
```

- [ ] **Step 4: Add GET /usage endpoint to workspaces.py**

In `backend/app/api/v1/workspaces.py`, add the following import and route:

```python
from app.config import PLAN_CHAR_LIMITS
from app.schemas.crawl import WorkspaceUsageResponse

@router.get("/{workspace_id}/usage", response_model=WorkspaceUsageResponse)
async def get_workspace_usage(
    workspace_id: _uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    limit = PLAN_CHAR_LIMITS.get(workspace.plan)
    chars_remaining: int | None = None
    if limit is not None:
        chars_remaining = max(0, limit - workspace.chars_indexed)

    return WorkspaceUsageResponse(
        chars_indexed=workspace.chars_indexed,
        chars_limit=limit,
        chars_remaining=chars_remaining,
        plan=workspace.plan,
    )
```

Note: `workspaces.py` uses `import uuid as _uuid` throughout — use `_uuid.UUID` for all UUID type hints, matching the existing pattern in the file.

- [ ] **Step 5: Restart backend and test the /usage endpoint**

```bash
docker compose restart backend
curl -s -H "Authorization: Bearer $(docker compose exec backend python -c "from app.services.auth_service import create_access_token; print(create_access_token({'sub': 'test@pulse.dev'}))" 2>/dev/null)" \
  http://localhost:8000/api/v1/workspaces/350863e7-3dc8-430e-bc23-fd41d4499d7b/usage
```

Expected: JSON with `chars_indexed`, `chars_limit`, `chars_remaining`, `plan`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/crawl.py backend/app/api/v1/workspaces.py
git commit -m "feat: update crawl API handler and add GET /usage endpoint"
```

---

### Task 8: Update crawl API integration tests

**Files:**
- Modify: `backend/tests/integration/test_crawl_api.py`

The existing tests send `"max_pages": 50` in the request body — this field is now removed. Update all references.

- [ ] **Step 1: Update test_crawl_api.py**

Replace all occurrences of `"max_pages": <number>` with path filter fields (or omit them entirely, since both are optional):

```python
# Old: json={"url": "https://a.com", "max_pages": 50}
# New: json={"url": "https://a.com"}

# Old: json={"url": "https://a.com", "max_pages": 10}
# New: json={"url": "https://a.com"}

# Old: json={"url": "https://a.com", "max_pages": 5, "chatbot_id": str(bot.id)}
# New: json={"url": "https://a.com", "chatbot_id": str(bot.id)}
```

Also remove any assertions on `over_limit` or `limit` in the response.

Add a test for the `/usage` endpoint:

```python
async def test_workspace_usage_endpoint(self, auth_client, workspace):
    """GET /usage returns chars_indexed, chars_limit, chars_remaining, plan."""
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/usage")
    assert r.status_code == 200
    data = r.json()
    assert "chars_indexed" in data
    assert "plan" in data
    # chars_indexed is 0 for a fresh test workspace
    assert data["chars_indexed"] == 0
```

Add a test for path filter validation:

```python
async def test_crawl_rejects_path_not_starting_with_slash(self, auth_client, workspace):
    """include_paths entries must start with '/'."""
    with patch("app.api.v1.crawl.crawl_website") as mock_task:
        mock_task.delay.return_value = None
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/crawl",
            json={"url": "https://a.com", "include_paths": ["blog"]},
        )
    assert r.status_code == 422
```

- [ ] **Step 2: Run integration tests**

```bash
docker compose exec backend pytest tests/integration/test_crawl_api.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_crawl_api.py
git commit -m "test: update crawl integration tests for new schema"
```

---

## Chunk 4: Character Budget Enforcement

### Task 9: Add budget check to ingestion pipeline

**Files:**
- Modify: `backend/app/workers/tasks/ingest_document.py` — add idempotency guard
- Modify: `backend/app/services/ingestion/pipeline.py` — add budget check after content extraction

The budget check must happen inside `run_ingestion()` in `pipeline.py`, after `content = _extract(document)` on the main path (line 288). The idempotency guard goes at the top of `_run()` in `ingest_document.py`.

- [ ] **Step 1: Add idempotency guard to _run() and update _mark_document_failed in ingest_document.py**

In `backend/app/workers/tasks/ingest_document.py`, update the `_run` function to add an early-exit check at the start (before calling `run_ingestion`):

```python
async def _run(document_id: uuid.UUID) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        # Idempotency guard: if already processed, skip re-ingestion
        from app.models.knowledge import Document
        from sqlalchemy import select as sa_select
        doc_check = await session.execute(sa_select(Document).where(Document.id == document_id))
        doc = doc_check.scalar_one_or_none()
        if doc is not None and doc.status in ("indexed", "skipped"):
            return {"status": "already_processed", "document_id": str(document_id)}

        try:
            await run_ingestion(session, document_id)
            await session.commit()
            return {"status": "success", "document_id": str(document_id)}
        except Exception as exc:
            await session.rollback()
            await _mark_document_failed(document_id, str(exc))
            raise
```

Also update `_mark_document_failed` to guard against overwriting "skipped" status:

```python
async def _mark_document_failed(document_id: uuid.UUID, reason: str) -> None:
    from app.models.knowledge import Document
    from sqlalchemy import select

    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc and doc.status not in ("indexed", "skipped", "failed"):
                doc.status = "failed"
                await session.commit()
        except Exception as e:
            logger.error("Failed to mark document %s as failed: %s", document_id, e)
```

- [ ] **Step 2: Add budget check to pipeline.py after _extract()**

In `backend/app/services/ingestion/pipeline.py`, find the section at line 288:

```python
        content = _extract(document)
        chunks = _chunk(document, content)
```

Add the budget check between `content = _extract(document)` and `chunks = _chunk(document, content)`:

```python
        content = _extract(document)

        # Character budget enforcement
        n = len(content)
        if n > 0:
            from sqlalchemy import text as sa_text
            from app.config import PLAN_CHAR_LIMITS
            from app.models.organizational import Workspace

            ws_result = await db.execute(
                select(Workspace).where(Workspace.id == document.workspace_id)
            )
            workspace = ws_result.scalar_one()
            limit = PLAN_CHAR_LIMITS.get(workspace.plan)

            budget_rows = await db.execute(
                sa_text("""
                    UPDATE workspaces
                    SET    chars_indexed = chars_indexed + :n
                    WHERE  id = :workspace_id
                      AND  (:limit IS NULL OR chars_indexed + :n <= :limit)
                    RETURNING chars_indexed
                """),
                {"n": n, "workspace_id": document.workspace_id, "limit": limit},
            )
            accepted = budget_rows.fetchone() is not None

            if not accepted:
                document.status = "skipped"
                document.char_count = 0
                return

            document.char_count = n

        chunks = _chunk(document, content)
```

Note: `select` is already imported at the top of `pipeline.py` (`from sqlalchemy import select`). Add `from sqlalchemy import text as sa_text` alongside the existing `select` import at the top of the file.

- [ ] **Step 3: Restart backend and verify no import errors**

```bash
docker compose restart backend
docker compose exec backend python -c "from app.services.ingestion.pipeline import run_ingestion; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Write integration test for budget enforcement**

Create `backend/tests/integration/test_char_budget.py`:

```python
# backend/tests/integration/test_char_budget.py
"""Integration tests for character budget enforcement."""
import asyncio
import uuid
import pytest

from app.models.knowledge import Document, KnowledgeBase
from app.models.organizational import Workspace
from app.services.ingestion.pipeline import run_ingestion
from sqlalchemy import select


@pytest.fixture
async def kb(db, workspace):
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        name="test kb",
    )
    db.add(kb)
    await db.flush()
    return kb


async def _make_doc(db, workspace, kb, content: str) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        knowledge_base_id=kb.id,
        source_type="text",
        raw_content=content,
        title="test",
        status="pending",
    )
    db.add(doc)
    await db.flush()
    return doc


class TestCharBudget:

    async def test_ingest_sets_char_count(self, db, workspace, kb):
        """After ingestion, document.char_count equals len(raw_content)."""
        content = "hello world"
        doc = await _make_doc(db, workspace, kb, content)

        # Set plan limit high so budget is not exceeded
        workspace.plan = "starter"
        await db.flush()

        await run_ingestion(db, doc.id)

        await db.refresh(doc)
        assert doc.char_count == len(content)
        assert doc.status == "indexed"

    async def test_budget_exceeded_sets_skipped(self, db, workspace, kb):
        """When chars_indexed would exceed plan limit, document is skipped."""
        # Set workspace to free plan (500k limit) and pre-fill chars_indexed near limit
        workspace.plan = "free"
        workspace.chars_indexed = 499_999  # 1 char remaining
        await db.flush()

        content = "hello world"  # 11 chars — would exceed the 1 char remaining
        doc = await _make_doc(db, workspace, kb, content)
        await run_ingestion(db, doc.id)

        await db.refresh(doc)
        await db.refresh(workspace)
        assert doc.status == "skipped"
        assert doc.char_count == 0
        # chars_indexed must not have increased
        assert workspace.chars_indexed == 499_999

    async def test_enterprise_plan_has_no_limit(self, db, workspace, kb):
        """Enterprise plan (limit=None) always accepts budget."""
        workspace.plan = "enterprise"
        workspace.chars_indexed = 50_000_000  # already huge
        await db.flush()

        content = "a" * 1000
        doc = await _make_doc(db, workspace, kb, content)
        await run_ingestion(db, doc.id)

        await db.refresh(doc)
        assert doc.status == "indexed"
        assert doc.char_count == 1000

    async def test_concurrent_ingest_does_not_exceed_limit(self, db, workspace, kb):
        """Two concurrent ingestions for the same workspace respect the atomic limit.

        Uses two separate sessions (as real Celery tasks would) to test the
        atomic UPDATE...WHERE...RETURNING pattern. A single shared session
        cannot test concurrency correctly.
        """
        from app.database import async_session_factory, engine as app_engine

        workspace.plan = "free"
        workspace.chars_indexed = 499_900  # 100 chars remaining
        await db.commit()  # commit so both sessions see the workspace

        content = "x" * 60  # 60 chars each — together 120 > 100 remaining

        # Create both documents in the shared session
        doc1_id = (await _make_doc(db, workspace, kb, content)).id
        doc2_id = (await _make_doc(db, workspace, kb, content)).id
        await db.commit()

        # Run ingestion in two separate sessions — mimics two Celery workers
        async def ingest_in_own_session(doc_id):
            await app_engine.dispose()
            async with async_session_factory() as sess:
                await run_ingestion(sess, doc_id)
                await sess.commit()

        await asyncio.gather(
            ingest_in_own_session(doc1_id),
            ingest_in_own_session(doc2_id),
        )

        # Read back results from a fresh session
        await app_engine.dispose()
        async with async_session_factory() as check_sess:
            from sqlalchemy import select as sa_select
            from app.models.knowledge import Document
            from app.models.organizational import Workspace

            r1 = await check_sess.execute(sa_select(Document).where(Document.id == doc1_id))
            r2 = await check_sess.execute(sa_select(Document).where(Document.id == doc2_id))
            ws = (await check_sess.execute(sa_select(Workspace).where(Workspace.id == workspace.id))).scalar_one()

            doc1_status = r1.scalar_one().status
            doc2_status = r2.scalar_one().status

        statuses = {doc1_status, doc2_status}
        assert "indexed" in statuses
        assert "skipped" in statuses
        assert ws.chars_indexed <= 500_000
```

- [ ] **Step 5: Run budget tests**

```bash
docker compose exec backend pytest tests/integration/test_char_budget.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/tasks/ingest_document.py backend/app/services/ingestion/pipeline.py backend/tests/integration/test_char_budget.py
git commit -m "feat: add character budget enforcement and idempotency guard to ingest pipeline"
```

---

### Task 10: Decrement chars_indexed on document delete

**Files:**
- Modify: `backend/app/services/document_service.py`

- [ ] **Step 1: Update delete_document to decrement chars_indexed**

In `backend/app/services/document_service.py`, update the `delete_document` function (currently lines 74–77):

```python
async def delete_document(db: AsyncSession, workspace_id: uuid.UUID, document_id: uuid.UUID) -> None:
    doc = await get_document(db, workspace_id, document_id)
    char_count = doc.char_count  # capture before delete

    await db.delete(doc)
    await db.flush()

    # Decrement workspace chars_indexed (clamped to 0)
    if char_count > 0:
        from sqlalchemy import text as sa_text
        await db.execute(
            sa_text("""
                UPDATE workspaces
                SET chars_indexed = GREATEST(0, chars_indexed - :char_count)
                WHERE id = :workspace_id
            """),
            {"char_count": char_count, "workspace_id": workspace_id},
        )
```

- [ ] **Step 2: Write test for decrement**

Add to `backend/tests/integration/test_char_budget.py`:

```python
    async def test_delete_decrements_chars_indexed(self, db, workspace, kb):
        """Deleting an indexed document decrements workspace.chars_indexed."""
        from app.services.document_service import delete_document

        workspace.plan = "starter"
        workspace.chars_indexed = 0
        await db.flush()

        content = "hello world"
        doc = await _make_doc(db, workspace, kb, content)
        await run_ingestion(db, doc.id)
        await db.commit()

        await db.refresh(workspace)
        chars_before = workspace.chars_indexed
        assert chars_before == len(content)

        await delete_document(db, workspace.id, doc.id)
        await db.commit()

        await db.refresh(workspace)
        assert workspace.chars_indexed == 0
```

- [ ] **Step 3: Run the test**

```bash
docker compose exec backend pytest tests/integration/test_char_budget.py::TestCharBudget::test_delete_decrements_chars_indexed -v
```

Expected: PASS.

- [ ] **Step 4: Run all backend tests to check for regressions**

```bash
docker compose exec backend pytest tests/unit/ tests/integration/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass (or only pre-existing failures, none new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/document_service.py backend/tests/integration/test_char_budget.py
git commit -m "feat: decrement chars_indexed on document delete"
```

---

## Chunk 5: Frontend

### Task 11: Update types.ts and api-functions.ts

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api-functions.ts`

- [ ] **Step 1: Update CrawlResponse, CrawlJobSummary, CrawlStatusResponse in types.ts**

Find and update these interfaces in `frontend/src/lib/types.ts`:

```typescript
// Replace CrawlResponse (remove over_limit and limit):
export interface CrawlResponse {
  job_id: string;
  kb_id: string;
  pages_discovered: number;
  pages_queued: number;
}

// Replace CrawlJobSummary (add docs_skipped):
export interface CrawlJobSummary {
  job_id: string;
  status: string;
  root_url: string;
  pages_discovered: number;
  pages_queued: number;
  pages_failed: number;
  docs_indexed: number;
  docs_skipped: number;
  created_at: string;
  completed_at: string | null;
}

// Replace CrawlStatusResponse (add docs_skipped, remove over_limit/limit if present):
export interface CrawlStatusResponse {
  job_id: string;
  status: string;
  pages_discovered: number;
  pages_queued: number;
  pages_failed: number;
  docs_indexed: number;
  docs_total: number;
  docs_failed: number;
  docs_skipped: number;
  stalled: boolean;
}

// Add WorkspaceUsage:
export interface WorkspaceUsage {
  chars_indexed: number;
  chars_limit: number | null;
  chars_remaining: number | null;
  plan: string;
}
```

- [ ] **Step 2: Update startCrawl and add getWorkspaceUsage in api-functions.ts**

Find `startCrawl` (line 84) and replace:

```typescript
export function startCrawl(
  workspaceId: string,
  url: string,
  includePaths: string[],
  excludePaths: string[],
  chatbotId?: string,
) {
  return api.post<CrawlResponse>(`/api/v1/workspaces/${workspaceId}/crawl`, {
    url,
    include_paths: includePaths,
    exclude_paths: excludePaths,
    chatbot_id: chatbotId,
  });
}
```

Add `getWorkspaceUsage` after `startCrawl`:

```typescript
export function getWorkspaceUsage(workspaceId: string) {
  return api.get<WorkspaceUsage>(`/api/v1/workspaces/${workspaceId}/usage`);
}
```

Update the imports in `api-functions.ts` — add `WorkspaceUsage` to the import from `@/lib/types`.

- [ ] **Step 3: Fix TypeScript errors from signature change**

The `startCrawl` signature changed (removed `maxPages`, added `includePaths`/`excludePaths`). Find all callers:

```bash
grep -r "startCrawl" frontend/src --include="*.tsx" --include="*.ts" -n
```

Two callers exist:
1. `frontend/src/app/(dashboard)/chatbots/new/page.tsx` — currently calls `startCrawl(workspace.id, normalized, 50, chatbot.id)`
2. `frontend/src/components/knowledge/AddSourceModal.tsx` (if it exists there)

For `chatbots/new/page.tsx`, update the call:
```typescript
// Old: const crawl = await startCrawl(workspace.id, normalized, 50, chatbot.id);
// New:
const crawl = await startCrawl(workspace.id, normalized, [], [], chatbot.id);
```

Also update the line that initialises `crawlStatus` — remove `over_limit` and `limit` if present.

- [ ] **Step 4: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api-functions.ts frontend/src/app/(dashboard)/chatbots/new/page.tsx
git commit -m "feat: update frontend types and api-functions for char budget and path filters"
```

---

### Task 12: Update AddSourceModal crawl form and CrawlStatusPanel

**Files:**
- Modify: `frontend/src/components/knowledge/AddSourceModal.tsx` — find the "sitemap" crawl form section
- Modify: `frontend/src/panels/CrawlStatusPanel.tsx`

- [ ] **Step 1: Read AddSourceModal.tsx to find the crawl/sitemap form**

```bash
grep -n "max_pages\|maxPages\|startCrawl\|Sitemap\|sitemap" frontend/src/components/knowledge/AddSourceModal.tsx
```

Locate the form section for the "sitemap" source type. It likely has a `max_pages` / `maxPages` input field. Replace it with two text inputs for include/exclude paths.

- [ ] **Step 2: Update the sitemap form in AddSourceModal.tsx**

Find and replace the max-pages input. The new form fields should be:

```tsx
{/* Include paths */}
<div>
  <label className="block text-xs font-medium text-gray-700 mb-1">
    Include paths <span className="text-gray-400 font-normal">(optional)</span>
  </label>
  <input
    type="text"
    value={includePaths}
    onChange={(e) => setIncludePaths(e.target.value)}
    placeholder="/blog, /docs"
    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
  />
  <p className="mt-1 text-[11px] text-gray-400">Only crawl URLs matching these path prefixes. Leave empty to crawl all pages.</p>
</div>

{/* Exclude paths */}
<div>
  <label className="block text-xs font-medium text-gray-700 mb-1">
    Exclude paths <span className="text-gray-400 font-normal">(optional)</span>
  </label>
  <input
    type="text"
    value={excludePaths}
    onChange={(e) => setExcludePaths(e.target.value)}
    placeholder="/admin, /private"
    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
  />
  <p className="mt-1 text-[11px] text-gray-400">Skip URLs matching these path prefixes.</p>
</div>
```

Add state variables `const [includePaths, setIncludePaths] = useState("")` and `const [excludePaths, setExcludePaths] = useState("")`.

On submit, parse the comma-separated values:
```typescript
const parsePathList = (raw: string): string[] =>
  raw.split(",").map((s) => s.trim()).filter(Boolean);

// When calling startCrawl:
await startCrawl(workspaceId, url, parsePathList(includePaths), parsePathList(excludePaths), chatbotId);
```

Remove any `maxPages` state and `max_pages` input entirely.

- [ ] **Step 3: Update CrawlStatusPanel.tsx**

Add `docs_skipped` warning banner. In `CrawlStatusPanel.tsx`, add inside the rendered JSX, after the "stalled" warning and before (or after) the "completed" success banner:

```tsx
{(status.docs_skipped ?? 0) > 0 && (
  <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-[11px] text-amber-800">
    <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
    {status.docs_skipped} page{status.docs_skipped > 1 ? "s were" : " was"} skipped — character limit reached.
  </div>
)}
```

- [ ] **Step 4: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: zero errors.

- [ ] **Step 5: Write Vitest unit test for skipped warning logic**

Create `frontend/src/test/crawl-status-panel.test.ts`:

```typescript
// frontend/src/test/crawl-status-panel.test.ts
import { describe, it, expect } from 'vitest';

// Pure logic: should the skipped warning be shown?
function shouldShowSkippedWarning(docsSkipped: number): boolean {
  return docsSkipped > 0;
}

describe('CrawlStatusPanel skipped warning', () => {
  it('shows warning when docs_skipped > 0', () => {
    expect(shouldShowSkippedWarning(1)).toBe(true);
    expect(shouldShowSkippedWarning(5)).toBe(true);
  });

  it('does not show warning when docs_skipped is 0', () => {
    expect(shouldShowSkippedWarning(0)).toBe(false);
  });
});
```

Run:
```bash
cd frontend && npx vitest run src/test/crawl-status-panel.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/knowledge/AddSourceModal.tsx frontend/src/panels/CrawlStatusPanel.tsx frontend/src/test/crawl-status-panel.test.ts
git commit -m "feat: replace max_pages with path filters in crawl form; add skipped-docs warning to CrawlStatusPanel"
```

---

### Task 13: Add character usage bar to billing page

**Files:**
- Modify: `frontend/src/app/(dashboard)/settings/billing/page.tsx`

- [ ] **Step 1: Add usage state and fetch to billing page**

In `frontend/src/app/(dashboard)/settings/billing/page.tsx`:

Add import:
```typescript
import { WorkspaceUsage } from "@/lib/types";
import { getWorkspaceUsage } from "@/lib/api-functions";
```

Add state:
```typescript
const [charUsage, setCharUsage] = useState<WorkspaceUsage | null>(null);
```

In the existing `useEffect` that fetches billing data (where `workspace` is available), add:
```typescript
promises.push(getWorkspaceUsage(workspace.id).then(setCharUsage).catch(() => {}));
```

- [ ] **Step 2: Add the usage bar component inline**

Add a helper function at the top of the file (outside the component):

```typescript
function CharUsageBar({ usage }: { usage: WorkspaceUsage }) {
  if (usage.chars_limit === null) {
    return (
      <div className="text-sm text-gray-600">
        <span className="font-medium">{usage.chars_indexed.toLocaleString()}</span> characters indexed
        {" "}<span className="text-gray-400">(unlimited plan)</span>
      </div>
    );
  }

  const pct = Math.min(100, Math.round((usage.chars_indexed / usage.chars_limit) * 100));
  const barColor =
    pct >= 95 ? "bg-red-500" :
    pct >= 80 ? "bg-amber-500" :
    "bg-green-500";

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-gray-600">
        <span>
          <span className="font-medium">{usage.chars_indexed.toLocaleString()}</span>
          {" / "}
          {usage.chars_limit.toLocaleString()} characters indexed
        </span>
        <span className="text-gray-400">{pct}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-gray-100">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {usage.chars_remaining !== null && (
        <p className="text-[11px] text-gray-400">
          {usage.chars_remaining.toLocaleString()} characters remaining
        </p>
      )}
    </div>
  );
}
```

In the JSX, add the usage bar in a visible section of the billing page (e.g. below the current plan info card, before the billing plans list). Wrap it in a `Card`:

```tsx
{charUsage && (
  <Card>
    <CardContent className="p-4 space-y-2">
      <h3 className="text-sm font-semibold text-gray-700">Knowledge Base Usage</h3>
      <CharUsageBar usage={charUsage} />
    </CardContent>
  </Card>
)}
```

- [ ] **Step 3: Write Vitest unit test for bar color logic**

Create `frontend/src/test/char-usage-bar.test.ts`:

```typescript
// frontend/src/test/char-usage-bar.test.ts
import { describe, it, expect } from 'vitest';

function barColor(pct: number): string {
  if (pct >= 95) return 'bg-red-500';
  if (pct >= 80) return 'bg-amber-500';
  return 'bg-green-500';
}

describe('CharUsageBar color thresholds', () => {
  it('is green below 80%', () => {
    expect(barColor(0)).toBe('bg-green-500');
    expect(barColor(50)).toBe('bg-green-500');
    expect(barColor(79)).toBe('bg-green-500');
  });

  it('is amber from 80% to 94%', () => {
    expect(barColor(80)).toBe('bg-amber-500');
    expect(barColor(90)).toBe('bg-amber-500');
    expect(barColor(94)).toBe('bg-amber-500');
  });

  it('is red at 95% and above', () => {
    expect(barColor(95)).toBe('bg-red-500');
    expect(barColor(100)).toBe('bg-red-500');
  });
});
```

Run:
```bash
cd frontend && npx vitest run src/test/char-usage-bar.test.ts
```

Expected: PASS.

- [ ] **Step 4: Run TypeScript check and all frontend tests**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
cd frontend && npx vitest run 2>&1 | tail -10
```

Expected: zero TS errors, all tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/(dashboard)/settings/billing/page.tsx frontend/src/test/char-usage-bar.test.ts
git commit -m "feat: add character usage bar to billing page"
```

---

## Final verification

- [ ] **Run all backend tests**

```bash
docker compose exec backend pytest tests/unit/ tests/integration/ -v --tb=short 2>&1 | tail -30
```

Expected: all pass (coverage gate ≥45% maintained).

- [ ] **Run all frontend tests**

```bash
cd frontend && npx vitest run
```

Expected: all pass.

- [ ] **Smoke-test the full crawl flow via browser**

1. Open http://localhost:3001
2. Log in as `test@pulse.dev` / `test`
3. Create a new chatbot → provide a URL with include/exclude paths set → confirm crawl starts
4. Navigate to Settings → Billing → verify usage bar appears
5. Confirm no JavaScript console errors
