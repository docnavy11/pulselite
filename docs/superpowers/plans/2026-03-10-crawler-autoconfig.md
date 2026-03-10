# Web Crawler & Auto-Configuration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a website crawler and LLM-powered auto-configuration service enabling "paste URL → live in 60 seconds."

**Architecture:** Six decoupled components — fetcher (httpx→Playwright), crawler (sitemap→BFS), crawl_service (orchestration), autoconfig (pure LLM), autoconfig_service (orchestration), plus API endpoints and a Celery task. Existing `ingest_document` pipeline is unchanged; crawl_service feeds it Documents with `source_type="text"` and pre-fetched `raw_content`.

**Tech Stack:** httpx, playwright (Python), trafilatura, defusedxml, beautifulsoup4, openai, SQLAlchemy async, FastAPI, Celery, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-10-crawler-autoconfig-design.md`

---

## Chunk 1: Foundation — Dependencies, DB, Models, Fetcher, Crawler

### Task 1: Add Playwright and BeautifulSoup to backend dependencies

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Add packages to pyproject.toml**

The project uses `backend/pyproject.toml` (not requirements.txt) for dependencies. Under `[project].dependencies`, add:
```toml
"playwright>=1.44.0",
"beautifulsoup4>=4.12.3",
```

- [ ] **Step 2: Add Playwright browser install to Dockerfile**

In `backend/Dockerfile`, after the `pip install` line, add:
```dockerfile
RUN playwright install chromium --with-deps
```

- [ ] **Step 3: Rebuild the backend container**

```bash
cd /Users/yvanveldeman/dev/pulselite
DOCKER_BUILDKIT=0 docker compose build backend
docker compose up -d backend
```

Expected: build completes, `docker compose ps` shows backend healthy.

- [ ] **Step 4: Verify playwright is importable**

```bash
docker compose exec backend python -c "from playwright.async_api import async_playwright; print('ok')"
```

Expected: prints `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/Dockerfile
git commit -m "chore: add playwright and beautifulsoup4 to backend deps"
```

---

### Task 2: DB Migration — crawl_jobs table + Chatbot columns

**Files:**
- Create: `backend/alembic/versions/2026_03_10_add_crawl_and_autoconfig.py`

- [ ] **Step 1: Create migration file**

```python
# backend/alembic/versions/2026_03_10_add_crawl_and_autoconfig.py
"""add crawl_jobs table and chatbot autoconfig fields

Revision ID: add_crawl_and_autoconfig
Revises: drop_enterprise_features
Create Date: 2026-03-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "add_crawl_and_autoconfig"
down_revision = "drop_enterprise_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("root_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("pages_discovered", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pages_queued", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pages_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("over_limit", sa.Boolean(), server_default="FALSE", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("chatbots", sa.Column("brand_color", sa.String(7), nullable=True))
    op.add_column("chatbots", sa.Column("welcome_message", sa.Text(), nullable=True))
    op.add_column("chatbots", sa.Column("suggested_questions", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("chatbots", "suggested_questions")
    op.drop_column("chatbots", "welcome_message")
    op.drop_column("chatbots", "brand_color")
    op.drop_table("crawl_jobs")
```

- [ ] **Step 2: Run migration on dev DB**

```bash
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade drop_enterprise_features -> add_crawl_and_autoconfig`

- [ ] **Step 3: Run migration on test DB**

First ensure the test DB exists (create it if this is first time):
```bash
docker compose exec postgres psql -U pulse -c "CREATE DATABASE pulse_test;" 2>/dev/null || true
```

Then run the migration:
```bash
docker compose exec backend bash -c "PYTHONPATH=/app POSTGRES_DB=pulse_test alembic upgrade head"
```

Expected: same output.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/2026_03_10_add_crawl_and_autoconfig.py
git commit -m "feat: add crawl_jobs table and chatbot autoconfig fields migration"
```

---

### Task 3: Add CrawlJob model and Chatbot fields to knowledge.py

**Files:**
- Modify: `backend/app/models/knowledge.py`

- [ ] **Step 1: Add new fields to Chatbot class**

In `backend/app/models/knowledge.py`, first add `String` to the existing sqlalchemy import line:
```python
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
```

Then inside the `Chatbot` class, after the `widget_config` line, add:

```python
    brand_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_questions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: Add CrawlJob model**

At the bottom of `backend/app/models/knowledge.py`, add:

```python
class CrawlJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crawl_jobs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)
    root_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    pages_discovered: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_queued: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_failed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    over_limit: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Note: `TimestampMixin` provides `created_at`. `TimestampUpdateMixin` would add `updated_at` too — use `TimestampMixin` here since we have explicit `started_at`/`completed_at`.

- [ ] **Step 3: Verify import works**

```bash
docker compose exec backend python -c "from app.models.knowledge import CrawlJob, Chatbot; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/knowledge.py
git commit -m "feat: add CrawlJob model and Chatbot autoconfig fields"
```

---

### Task 4: fetcher.py + unit tests

**Files:**
- Create: `backend/app/services/fetcher.py`
- Create: `backend/tests/unit/test_fetcher.py`

- [ ] **Step 1: Write failing unit tests**

```python
# backend/tests/unit/test_fetcher.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.fetcher import FetchResult, fetch, extract_brand_color, _extract_theme_color


# ── extract_brand_color ───────────────────────────────────────────────────────

def test_extract_theme_color_from_meta():
    html = '<meta name="theme-color" content="#4F46E5">'
    assert _extract_theme_color(html) == "#4F46E5"

def test_extract_theme_color_reversed_attrs():
    html = '<meta content="#123ABC" name="theme-color">'
    assert _extract_theme_color(html) == "#123ABC"

def test_extract_theme_color_css_variable():
    html = "<style>:root { --primary: #6366f1; }</style>"
    assert _extract_theme_color(html) == "#6366f1"

def test_extract_theme_color_none_when_missing():
    assert _extract_theme_color("<html><body>no color</body></html>") is None

def test_extract_brand_color_empty_html():
    assert extract_brand_color("") is None

def test_extract_brand_color_none_html():
    assert extract_brand_color("") is None


# ── fetch: SSRF guard ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="http or https"):
        await fetch("file:///etc/passwd")

@pytest.mark.asyncio
async def test_fetch_rejects_ftp():
    with pytest.raises(ValueError, match="http or https"):
        await fetch("ftp://evil.com/file")


# ── fetch: httpx path ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_result_on_200():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><title>Acme</title><body>lots of content here " + "x" * 600 + "</body></html>"

    with patch("app.services.fetcher.trafilatura.extract", return_value="lots of content here " + "x" * 600):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch("https://example.com")

    assert result.status_code == 200
    assert result.title == "Acme"
    assert result.used_playwright is False
    assert len(result.text) > 500


@pytest.mark.asyncio
async def test_fetch_triggers_playwright_when_text_thin():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>thin</body></html>"

    with patch("app.services.fetcher.trafilatura.extract", return_value="thin"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch("app.services.fetcher._fetch_with_playwright", new_callable=AsyncMock) as mock_pw:
                mock_pw.return_value = ("<html><body>" + "rich content " * 100 + "</body></html>", "rich content " * 100)
                result = await fetch("https://example.com")

    assert result.used_playwright is True
    assert len(result.text) > 500


@pytest.mark.asyncio
async def test_fetch_returns_httpx_result_when_playwright_fails():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>thin</body></html>"

    with patch("app.services.fetcher.trafilatura.extract", return_value="thin"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch("app.services.fetcher._fetch_with_playwright", side_effect=Exception("browser crash")):
                result = await fetch("https://example.com")

    # Should return httpx result, not raise
    assert result.status_code == 200
    assert result.used_playwright is False


@pytest.mark.asyncio
async def test_fetch_returns_empty_on_http_error():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value = mock_client

        result = await fetch("https://example.com")

    assert result.text == ""
    assert result.html == ""
    assert result.status_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest tests/unit/test_fetcher.py -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` — `fetcher` doesn't exist yet.

- [ ] **Step 3: Create fetcher.py**

```python
# backend/app/services/fetcher.py
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import trafilatura

logger = logging.getLogger(__name__)

_PLAYWRIGHT_THRESHOLD = 500
_USER_AGENT = "Mozilla/5.0 (compatible; PulseliteBot/1.0)"


@dataclass
class FetchResult:
    url: str
    html: str
    text: str
    title: str | None
    theme_color: str | None
    status_code: int
    used_playwright: bool


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must be http or https, got: {url!r}")


def _extract_title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_theme_color(html: str) -> str | None:
    """Extract hex color from meta theme-color or --primary CSS variable."""
    m = re.search(
        r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']theme-color["\']',
            html, re.IGNORECASE,
        )
    if m:
        color = m.group(1).strip()
        if re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", color):
            return color
    css_m = re.search(r"--primary\s*:\s*(#[0-9a-fA-F]{3,6})", html)
    if css_m:
        return css_m.group(1)
    return None


def extract_brand_color(html: str) -> str | None:
    """Public wrapper — returns None for empty input."""
    if not html:
        return None
    return _extract_theme_color(html)


async def _fetch_with_playwright(url: str) -> tuple[str, str]:
    """Returns (html, text). Caller handles exceptions."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(extra_http_headers={"User-Agent": _USER_AGENT})
            await page.goto(url, timeout=30_000)
            await page.wait_for_load_state("networkidle", timeout=15_000)
            html = await page.content()
            text = trafilatura.extract(html, include_comments=False, include_tables=True, output_format="txt") or ""
            return html, text
        finally:
            await browser.close()


async def fetch(url: str) -> FetchResult:
    """Fetch URL content. Falls back to Playwright when text < 500 chars."""
    _validate_url(url)

    html = ""
    text = ""
    status_code = 0

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=10.0,
        ) as client:
            response = await client.get(url)
            status_code = response.status_code
            if response.status_code < 400:
                html = response.text
                text = trafilatura.extract(
                    html, include_comments=False, include_tables=True, output_format="txt"
                ) or ""
    except Exception as exc:
        logger.warning("httpx fetch failed for %s: %s", url, exc)
        return FetchResult(
            url=url, html="", text="", title=None,
            theme_color=None, status_code=0, used_playwright=False,
        )

    used_playwright = False
    if len(text) < _PLAYWRIGHT_THRESHOLD:
        try:
            html, text = await _fetch_with_playwright(url)
            used_playwright = True
        except Exception as exc:
            logger.warning("Playwright fallback failed for %s: %s", url, exc)

    return FetchResult(
        url=url,
        html=html,
        text=text,
        title=_extract_title(html),
        theme_color=_extract_theme_color(html),
        status_code=status_code,
        used_playwright=used_playwright,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend pytest tests/unit/test_fetcher.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fetcher.py backend/tests/unit/test_fetcher.py
git commit -m "feat: add fetcher service with httpx+playwright fallback"
```

---

### Task 5: crawler.py + unit tests

**Files:**
- Create: `backend/app/services/crawler.py`
- Create: `backend/tests/unit/test_crawler.py`

- [ ] **Step 1: Write failing unit tests**

```python
# backend/tests/unit/test_crawler.py
import pytest
from unittest.mock import AsyncMock, patch

from app.services.crawler import CrawlResult, _normalize, _same_domain, discover_urls
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
        result = await discover_urls("https://a.com", max_pages=10)

    assert result.used_sitemap is True
    assert len(result.urls) == 4
    assert result.over_limit is False


@pytest.mark.asyncio
async def test_over_limit_flag():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/p1</loc></url>
      <url><loc>https://a.com/p2</loc></url>
      <url><loc>https://a.com/p3</loc></url>
      <url><loc>https://a.com/p4</loc></url>
      <url><loc>https://a.com/p5</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        result = await discover_urls("https://a.com", max_pages=3)

    assert result.over_limit is True
    assert result.total_discovered == 5
    assert len(result.urls) == 3


@pytest.mark.asyncio
async def test_sitemap_not_found_falls_back_to_bfs():
    page_html = """<html><body>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
    </body></html>"""

    call_count = {"n": 0}

    async def mock_fetch(url: str) -> FetchResult:
        call_count["n"] += 1
        if "sitemap" in url:
            return FetchResult(url=url, html="", text="", title=None,
                               theme_color=None, status_code=404, used_playwright=False)
        return FetchResult(url=url, html=page_html, text="content", title=None,
                           theme_color=None, status_code=200, used_playwright=False)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        result = await discover_urls("https://a.com", max_pages=10)

    assert result.used_sitemap is False
    assert "https://a.com/" in result.urls or "https://a.com" in result.urls


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
        result = await discover_urls("https://a.com", max_pages=20)

    assert all("other.com" not in u for u in result.urls)


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
        result = await discover_urls("https://a.com", max_pages=20)

    assert not any("foo=bar" in u for u in result.urls)
    assert any("clean" in u for u in result.urls)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest tests/unit/test_crawler.py -v 2>&1 | head -20
```

Expected: `ImportError` — `crawler` doesn't exist yet.

- [ ] **Step 3: Create crawler.py**

```python
# backend/app/services/crawler.py
import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse

import defusedxml.ElementTree as ET

from app.services.fetcher import FetchResult, fetch

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    urls: list[str]
    total_discovered: int
    over_limit: bool
    used_sitemap: bool


def _normalize(url: str) -> str:
    """Strip fragment and query string; normalize trailing slash."""
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))


def _same_domain(url: str, root_domain: str) -> bool:
    return urlparse(url).netloc == root_domain


async def _discover_via_sitemap(root_url: str) -> list[str] | None:
    sitemap_url = root_url.rstrip("/") + "/sitemap.xml"
    result: FetchResult = await fetch(sitemap_url)
    if result.status_code != 200 or not result.html:
        return None

    try:
        root_el = ET.fromstring(result.html.encode())
    except Exception:
        return None

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls: list[str] = []

    # Sitemap index: recurse into child sitemaps
    for sitemap_el in root_el.findall(".//sm:sitemap/sm:loc", ns):
        loc_text = sitemap_el.text
        if not loc_text:
            continue
        child = await fetch(loc_text.strip())
        if child.status_code == 200 and child.html:
            try:
                child_root = ET.fromstring(child.html.encode())
                for loc in child_root.findall(".//sm:url/sm:loc", ns):
                    if loc.text:
                        urls.append(loc.text.strip())
            except Exception:
                pass

    # Regular sitemap entries
    for loc in root_el.findall(".//sm:url/sm:loc", ns):
        if loc.text:
            urls.append(loc.text.strip())

    return urls if urls else None


async def _discover_via_bfs(root_url: str, max_depth: int = 3) -> list[str]:
    from bs4 import BeautifulSoup

    root_domain = urlparse(root_url).netloc
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(root_url, 0)]
    found: list[str] = []

    while queue:
        url, depth = queue.pop(0)
        norm = _normalize(url)
        if norm in visited:
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
            # Drop query strings entirely
            if parsed.query:
                continue
            norm_link = _normalize(absolute)
            if _same_domain(norm_link, root_domain) and norm_link not in visited:
                queue.append((norm_link, depth + 1))

    return found


async def discover_urls(root_url: str, max_pages: int) -> CrawlResult:
    """Discover all URLs under root_url up to max_pages."""
    urls: list[str] = []
    used_sitemap = False

    sitemap_urls = await _discover_via_sitemap(root_url)
    if sitemap_urls and len(sitemap_urls) >= 3:
        root_domain = urlparse(root_url).netloc
        urls = [u for u in sitemap_urls if _same_domain(u, root_domain)]
        used_sitemap = True
    else:
        urls = await _discover_via_bfs(root_url)

    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        n = _normalize(u)
        if n not in seen:
            seen.add(n)
            deduped.append(u)

    total = len(deduped)
    return CrawlResult(
        urls=deduped[:max_pages],
        total_discovered=total,
        over_limit=total > max_pages,
        used_sitemap=used_sitemap,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend pytest tests/unit/test_crawler.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/crawler.py backend/tests/unit/test_crawler.py
git commit -m "feat: add crawler service with sitemap+BFS discovery"
```

---

## Chunk 2: Crawl Service, Celery Task, API

### Task 6: crawl_service.py

**Files:**
- Create: `backend/app/services/crawl_service.py`

- [ ] **Step 1: Create crawl_service.py**

```python
# backend/app/services/crawl_service.py
import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import CrawlJob, Document, KnowledgeBase
from app.services.crawler import discover_urls
from app.services.fetcher import FetchResult, fetch

logger = logging.getLogger(__name__)

_FETCH_CONCURRENCY = 5  # max parallel HTTP fetches


@dataclass
class CrawlStartResult:
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int
    over_limit: bool
    limit: int


async def start_crawl(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    url: str,
    max_pages: int,
    kb_id: uuid.UUID | None = None,
) -> CrawlStartResult:
    from app.workers.tasks.ingest_document import ingest_document

    # 1. Discover URLs
    crawl_result = await discover_urls(url, max_pages)

    # 2. Create KB if not provided
    if kb_id is None:
        domain = urlparse(url).netloc
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        kb = KnowledgeBase(workspace_id=workspace_id, name=f"{domain} — crawled {date_str}")
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

    # 3. Create CrawlJob and COMMIT before queuing tasks
    job = CrawlJob(
        workspace_id=workspace_id,
        kb_id=kb_id,
        root_url=url,
        status="pending",
        pages_discovered=crawl_result.total_discovered,
        max_pages=max_pages,
        over_limit=crawl_result.over_limit,
    )
    db.add(job)
    await db.flush()
    await db.commit()       # Celery workers need to read this row
    await db.refresh(job)   # re-attach expired object after commit (required for async sessions)

    # 4. Fetch all URLs concurrently with bounded parallelism
    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

    async def _fetch_one(page_url: str) -> FetchResult:
        async with semaphore:
            return await fetch(page_url)

    fetch_results = await asyncio.gather(
        *[_fetch_one(u) for u in crawl_result.urls],
        return_exceptions=True,
    )

    # 5. Create Documents and queue ingestion
    pages_queued = 0
    pages_failed = 0

    for page_url, result in zip(crawl_result.urls, fetch_results):
        if isinstance(result, Exception):
            logger.warning("Fetch exception %s: %s", page_url, result)
            pages_failed += 1
            continue
        if result.status_code >= 400 or not result.text:
            logger.warning("Skipping %s (status=%d)", page_url, result.status_code)
            pages_failed += 1
            continue

        doc = Document(
            workspace_id=workspace_id,
            knowledge_base_id=kb_id,
            source_type="text",       # pre-fetched; pipeline reads raw_content directly
            source_url=page_url,
            raw_content=result.text,
            title=result.title,
            status="pending",
        )
        db.add(doc)
        await db.flush()
        ingest_document.delay(str(doc.id))
        pages_queued += 1

    # 6. Update CrawlJob
    job.pages_queued = pages_queued
    job.pages_failed = pages_failed
    job.status = "running"
    await db.commit()

    return CrawlStartResult(
        job_id=str(job.id),
        kb_id=str(kb_id),
        pages_discovered=crawl_result.total_discovered,
        pages_queued=pages_queued,
        over_limit=crawl_result.over_limit,
        limit=max_pages,
    )
```

- [ ] **Step 2: Verify import**

```bash
docker compose exec backend python -c "from app.services.crawl_service import start_crawl; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/crawl_service.py
git commit -m "feat: add crawl_service orchestrator"
```

---

### Task 7: crawl_website Celery task

**Files:**
- Create: `backend/app/workers/tasks/crawl_website.py`

- [ ] **Step 1: Create the task**

```python
# backend/app/workers/tasks/crawl_website.py
import asyncio
import uuid

from app.database import async_session_factory, engine
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_website(
    self,
    workspace_id: str,
    url: str,
    max_pages: int,
    kb_id: str | None = None,
) -> dict:
    try:
        result = asyncio.run(
            _run(uuid.UUID(workspace_id), url, max_pages, uuid.UUID(kb_id) if kb_id else None)
        )
        return result
    except Exception as exc:
        self.retry(exc=exc)


async def _run(
    workspace_id: uuid.UUID,
    url: str,
    max_pages: int,
    kb_id: uuid.UUID | None,
) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        from app.models.knowledge import CrawlJob
        from app.services.crawl_service import start_crawl
        from sqlalchemy import select
        from datetime import datetime, timezone

        try:
            result = await start_crawl(session, workspace_id, url, max_pages, kb_id)
            # Mark job started_at (crawl_service already set status=running)
            job_result = await session.execute(
                select(CrawlJob).where(CrawlJob.id == uuid.UUID(result.job_id))
            )
            job = job_result.scalar_one_or_none()
            if job:
                job.started_at = datetime.now(timezone.utc)
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
            return {"status": "success", "job_id": result.job_id, "pages_queued": result.pages_queued}
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 2: Verify import**

```bash
docker compose exec backend python -c "from app.workers.tasks.crawl_website import crawl_website; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks/crawl_website.py
git commit -m "feat: add crawl_website Celery task"
```

---

### Task 8: Crawl API schemas, router, and main.py registration

**Files:**
- Create: `backend/app/schemas/crawl.py`
- Create: `backend/app/api/v1/crawl.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create Pydantic schemas**

```python
# backend/app/schemas/crawl.py
import uuid
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator


class CrawlRequest(BaseModel):
    url: str
    max_pages: int
    knowledge_base_id: Optional[uuid.UUID] = None

    @field_validator("max_pages")
    @classmethod
    def max_pages_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_pages must be at least 1")
        return v

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must be http or https")
        return v


class CrawlResponse(BaseModel):
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int
    over_limit: bool
    limit: int


class CrawlJobStatusResponse(BaseModel):
    job_id: str
    kb_id: str
    status: str
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    over_limit: bool
    limit: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
```

- [ ] **Step 2: Create crawl API router**

```python
# backend/app/api/v1/crawl.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.models.knowledge import CrawlJob
from app.schemas.crawl import CrawlJobStatusResponse, CrawlRequest, CrawlResponse
from app.services.crawl_service import start_crawl

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["crawl"])


@router.post("/crawl", response_model=CrawlResponse, status_code=201)
async def crawl_website_endpoint(
    body: CrawlRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await start_crawl(db, workspace_id, body.url, body.max_pages, body.knowledge_base_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return CrawlResponse(
        job_id=result.job_id,
        kb_id=result.kb_id,
        pages_discovered=result.pages_discovered,
        pages_queued=result.pages_queued,
        over_limit=result.over_limit,
        limit=result.limit,
    )


@router.get("/crawl/{job_id}", response_model=CrawlJobStatusResponse)
async def get_crawl_status(
    job_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.workspace_id == workspace_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found")
    return CrawlJobStatusResponse(
        job_id=str(job.id),
        kb_id=str(job.kb_id),
        status=job.status,
        pages_discovered=job.pages_discovered,
        pages_queued=job.pages_queued,
        pages_failed=job.pages_failed,
        over_limit=job.over_limit,
        limit=job.max_pages,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )
```

- [ ] **Step 3: Register router in main.py**

In `backend/app/main.py`, add to the imports block:
```python
from app.api.v1 import crawl
```

Then add after the existing `include_router` lines:
```python
application.include_router(crawl.router, prefix="/api/v1")
```

- [ ] **Step 4: Restart backend and verify routes appear**

```bash
docker compose restart backend
curl -s http://localhost:8000/api/docs | python3 -c "import sys,json; d=json.load(sys.stdin); print([p for p in d['paths'] if 'crawl' in p])"
```

Expected: `['/api/v1/workspaces/{workspace_id}/crawl', '/api/v1/workspaces/{workspace_id}/crawl/{job_id}']`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/crawl.py backend/app/api/v1/crawl.py backend/app/main.py
git commit -m "feat: add crawl API endpoints and schemas"
```

---

### Task 9: Integration tests for crawl API

**Files:**
- Create: `backend/tests/integration/test_crawl_api.py`

- [ ] **Step 1: Create integration tests**

```python
# backend/tests/integration/test_crawl_api.py
"""Integration tests for POST /crawl and GET /crawl/{job_id}."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.crawl_service import CrawlStartResult
from app.services.crawler import CrawlResult
from app.services.fetcher import FetchResult


def _make_fetch(text: str = "content " * 100) -> FetchResult:
    return FetchResult(url="https://a.com/page", html="<html></html>",
                       text=text, title="Page", theme_color=None,
                       status_code=200, used_playwright=False)


class TestCrawlEndpoint:

    async def test_crawl_creates_kb_and_job(self, auth_client, workspace):
        """POST /crawl creates a KnowledgeBase and CrawlJob, returns job_id."""
        mock_crawl = CrawlResult(
            urls=["https://a.com/", "https://a.com/about"],
            total_discovered=2,
            over_limit=False,
            used_sitemap=False,
        )
        with patch("app.services.crawl_service.discover_urls", return_value=mock_crawl):
            with patch("app.services.crawl_service.fetch", return_value=_make_fetch()):
                with patch("app.workers.tasks.ingest_document.ingest_document.delay"):
                    r = await auth_client.post(
                        f"/api/v1/workspaces/{workspace.id}/crawl",
                        json={"url": "https://a.com", "max_pages": 50},
                    )

        assert r.status_code == 201
        data = r.json()
        assert "job_id" in data
        assert "kb_id" in data
        assert data["pages_discovered"] == 2
        assert data["pages_queued"] == 2
        assert data["over_limit"] is False

    async def test_crawl_reports_over_limit(self, auth_client, workspace):
        mock_crawl = CrawlResult(
            urls=["https://a.com/p1", "https://a.com/p2"],
            total_discovered=10,
            over_limit=True,
            used_sitemap=True,
        )
        with patch("app.services.crawl_service.discover_urls", return_value=mock_crawl):
            with patch("app.services.crawl_service.fetch", return_value=_make_fetch()):
                with patch("app.workers.tasks.ingest_document.ingest_document.delay"):
                    r = await auth_client.post(
                        f"/api/v1/workspaces/{workspace.id}/crawl",
                        json={"url": "https://a.com", "max_pages": 2},
                    )

        assert r.status_code == 201
        data = r.json()
        assert data["over_limit"] is True
        assert data["pages_discovered"] == 10
        assert data["limit"] == 2

    async def test_crawl_documents_use_source_type_text(self, db, auth_client, workspace):
        """Crawled Documents must have source_type='text' (not 'url') to avoid re-fetch."""
        from sqlalchemy import select
        from app.models.knowledge import Document

        mock_crawl = CrawlResult(
            urls=["https://a.com/"],
            total_discovered=1,
            over_limit=False,
            used_sitemap=False,
        )
        with patch("app.services.crawl_service.discover_urls", return_value=mock_crawl):
            with patch("app.services.crawl_service.fetch", return_value=_make_fetch()):
                with patch("app.workers.tasks.ingest_document.ingest_document.delay"):
                    r = await auth_client.post(
                        f"/api/v1/workspaces/{workspace.id}/crawl",
                        json={"url": "https://a.com", "max_pages": 5},
                    )

        assert r.status_code == 201
        result = await db.execute(
            select(Document).where(Document.workspace_id == workspace.id)
        )
        docs = result.scalars().all()
        assert len(docs) == 1
        assert docs[0].source_type == "text"
        assert docs[0].raw_content is not None

    async def test_get_crawl_status(self, auth_client, workspace):
        """GET /crawl/{job_id} returns job status."""
        mock_crawl = CrawlResult(
            urls=["https://a.com/"],
            total_discovered=1,
            over_limit=False,
            used_sitemap=False,
        )
        with patch("app.services.crawl_service.discover_urls", return_value=mock_crawl):
            with patch("app.services.crawl_service.fetch", return_value=_make_fetch()):
                with patch("app.workers.tasks.ingest_document.ingest_document.delay"):
                    post_r = await auth_client.post(
                        f"/api/v1/workspaces/{workspace.id}/crawl",
                        json={"url": "https://a.com", "max_pages": 5},
                    )
        job_id = post_r.json()["job_id"]

        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/crawl/{job_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("pending", "running", "completed")

    async def test_get_crawl_status_404_unknown_job(self, auth_client, workspace):
        import uuid
        r = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/crawl/{uuid.uuid4()}"
        )
        assert r.status_code == 404

    async def test_crawl_invalid_url_scheme(self, auth_client, workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/crawl",
            json={"url": "ftp://evil.com", "max_pages": 10},
        )
        assert r.status_code == 422

    async def test_crawl_max_pages_zero_rejected(self, auth_client, workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/crawl",
            json={"url": "https://a.com", "max_pages": 0},
        )
        assert r.status_code == 422
```

- [ ] **Step 2: Run integration tests**

```bash
docker compose exec backend pytest tests/integration/test_crawl_api.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_crawl_api.py
git commit -m "test: add crawl API integration tests"
```

---

### Task 10: Tenant isolation tests for crawl

**Files:**
- Modify: `backend/tests/integration/test_tenant_isolation.py`

- [ ] **Step 1: Add crawl isolation tests to the appropriate classes**

In `backend/tests/integration/test_tenant_isolation.py`:

Add to `TestWorkspaceSubstitutionWrites` (POST goes here — it's a write operation):
```python
    async def test_cannot_post_crawl_to_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{second_workspace.id}/crawl",
            json={"url": "https://example.com", "max_pages": 5},
        )
        assert r.status_code == 403
```

Add to `TestWorkspaceSubstitution` (GET goes here — it's a read operation):
```python
    async def test_cannot_get_crawl_status_in_other_workspace(self, auth_client, second_workspace):
        import uuid
        r = await auth_client.get(
            f"/api/v1/workspaces/{second_workspace.id}/crawl/{uuid.uuid4()}"
        )
        assert r.status_code == 403
```

- [ ] **Step 2: Run tenant isolation tests**

```bash
docker compose exec backend pytest tests/integration/test_tenant_isolation.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_tenant_isolation.py
git commit -m "test: add crawl tenant isolation tests"
```

---

## Chunk 3: Auto-Configuration

### Task 11: autoconfig.py + unit tests

**Files:**
- Create: `backend/app/services/autoconfig.py`
- Create: `backend/tests/unit/test_autoconfig.py`

- [ ] **Step 1: Write failing unit tests**

```python
# backend/tests/unit/test_autoconfig.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.autoconfig import AutoConfigResult, extract_brand_color, generate


# ── extract_brand_color ───────────────────────────────────────────────────────

def test_brand_color_empty_html():
    assert extract_brand_color("") is None

def test_brand_color_from_meta():
    html = '<meta name="theme-color" content="#4F46E5">'
    assert extract_brand_color(html) == "#4F46E5"

def test_brand_color_from_css_var():
    html = "<style>:root { --primary: #6366f1; }</style>"
    assert extract_brand_color(html) == "#6366f1"

def test_brand_color_none_when_not_found():
    assert extract_brand_color("<html><body>nothing</body></html>") is None


# ── generate ──────────────────────────────────────────────────────────────────

def _mock_openai_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


VALID_JSON = json.dumps({
    "name": "Acme Bot",
    "welcome_message": "Hi there!",
    "system_prompt": "You help with Acme products.",
    "suggested_questions": ["Q1?", "Q2?", "Q3?", "Q4?"],
    "fallback_message": "I don't know, sorry.",
})


@pytest.mark.asyncio
async def test_generate_returns_all_fields():
    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(VALID_JSON)
        )
        result = await generate(["chunk one", "chunk two"], "<html></html>")

    assert isinstance(result, AutoConfigResult)
    assert result.name == "Acme Bot"
    assert result.welcome_message == "Hi there!"
    assert len(result.suggested_questions) == 4
    assert result.fallback_message == "I don't know, sorry."


@pytest.mark.asyncio
async def test_generate_retries_on_bad_json():
    call_count = {"n": 0}

    async def mock_create(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _mock_openai_response("not json at all")
        return _mock_openai_response(VALID_JSON)

    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = mock_create
        result = await generate(["chunk"], "")

    assert call_count["n"] == 2
    assert result.name == "Acme Bot"


@pytest.mark.asyncio
async def test_generate_raises_after_two_bad_json_responses():
    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response("still not json")
        )
        with pytest.raises(RuntimeError, match="valid JSON"):
            await generate(["chunk"], "")


@pytest.mark.asyncio
async def test_generate_pads_short_suggested_questions():
    short_json = json.dumps({
        "name": "Bot",
        "welcome_message": "Hi",
        "system_prompt": "Help",
        "suggested_questions": ["Only one?"],
        "fallback_message": "Dunno",
    })
    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(short_json)
        )
        result = await generate(["chunk"], "")

    assert len(result.suggested_questions) == 4


@pytest.mark.asyncio
async def test_generate_extracts_brand_color_from_homepage_html():
    html = '<meta name="theme-color" content="#FF5733">'
    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(VALID_JSON)
        )
        result = await generate(["chunk"], html)

    assert result.brand_color == "#FF5733"


@pytest.mark.asyncio
async def test_generate_brand_color_none_for_empty_html():
    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(VALID_JSON)
        )
        result = await generate(["chunk"], "")

    assert result.brand_color is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest tests/unit/test_autoconfig.py -v 2>&1 | head -20
```

Expected: `ImportError` — `autoconfig` doesn't exist yet.

- [ ] **Step 3: Create autoconfig.py**

```python
# backend/app/services/autoconfig.py
import json
import logging
import random
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_SAMPLE_FIRST = 5
_SAMPLE_MAX = 20

_SYSTEM_PROMPT = """You are a configuration assistant. Given website content, generate a JSON config for a customer support chatbot.

Return ONLY valid JSON (no markdown, no explanation) with these exact keys:
{
  "name": "string (bot name, 2-4 words)",
  "welcome_message": "string (friendly greeting, 1 sentence)",
  "system_prompt": "string (instructions for the bot, max 300 words)",
  "suggested_questions": ["string", "string", "string", "string"],
  "fallback_message": "string (what to say when bot cannot answer, 1 sentence)"
}"""


@dataclass
class AutoConfigResult:
    name: str
    welcome_message: str
    system_prompt: str
    suggested_questions: list[str]
    fallback_message: str
    brand_color: str | None


def extract_brand_color(html: str) -> str | None:
    """Extract hex brand color from meta theme-color or CSS --primary variable."""
    if not html:
        return None
    m = re.search(
        r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']theme-color["\']',
            html, re.IGNORECASE,
        )
    if m:
        color = m.group(1).strip()
        if re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", color):
            return color
    css_m = re.search(r"--primary\s*:\s*(#[0-9a-fA-F]{3,6})", html)
    if css_m:
        return css_m.group(1)
    return None


def _sample_chunks(chunks: list[str]) -> list[str]:
    first = chunks[:_SAMPLE_FIRST]
    rest = chunks[_SAMPLE_FIRST:]
    remainder = _SAMPLE_MAX - len(first)
    if remainder > 0 and rest:
        return first + random.sample(rest, min(len(rest), remainder))
    return first


async def generate(chunks: list[str], homepage_html: str) -> AutoConfigResult:
    """Generate chatbot config from content chunks and homepage HTML."""
    sampled = _sample_chunks(chunks)
    content_preview = "\n\n---\n\n".join(sampled)

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def _call(strict: bool) -> str:
        extra = "\nRespond with ONLY a JSON object. No markdown, no explanation." if strict else ""
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT + extra},
                {"role": "user", "content": f"Website content:\n\n{content_preview}"},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return resp.choices[0].message.content or ""

    raw = await _call(strict=False)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("autoconfig: LLM returned non-JSON, retrying with strict prompt")
        raw = await _call(strict=True)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"autoconfig: LLM failed to return valid JSON: {e}") from e

    qs = data.get("suggested_questions", [])
    if not isinstance(qs, list):
        qs = []
    qs = [str(q) for q in qs[:4]]
    while len(qs) < 4:
        qs.append("How can you help me?")

    return AutoConfigResult(
        name=str(data.get("name", "Support Bot")),
        welcome_message=str(data.get("welcome_message", "Hi! How can I help you?")),
        system_prompt=str(data.get("system_prompt", "")),
        suggested_questions=qs,
        fallback_message=str(data.get("fallback_message", "I'm not sure. Want to connect with our team?")),
        brand_color=extract_brand_color(homepage_html),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend pytest tests/unit/test_autoconfig.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/autoconfig.py backend/tests/unit/test_autoconfig.py
git commit -m "feat: add autoconfig service with LLM config generation"
```

---

### Task 12: autoconfig_service.py

**Files:**
- Create: `backend/app/services/autoconfig_service.py`

- [ ] **Step 1: Create autoconfig_service.py**

```python
# backend/app/services/autoconfig_service.py
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Chatbot, Chunk, Document
from app.services.autoconfig import generate
from app.services.fetcher import fetch

logger = logging.getLogger(__name__)

_MAX_CHUNKS = 20


async def run(
    db: AsyncSession,
    chatbot_id: uuid.UUID,
    kb_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Chatbot:
    # 1. Verify chatbot belongs to workspace
    r = await db.execute(
        select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace_id)
    )
    chatbot = r.scalar_one_or_none()
    if chatbot is None:
        raise ValueError("Chatbot not found")

    # 2. Fetch chunks ordered by chunk_index (deterministic)
    chunks_r = await db.execute(
        select(Chunk)
        .where(Chunk.knowledge_base_id == kb_id, Chunk.workspace_id == workspace_id)
        .order_by(Chunk.chunk_index.asc())
        .limit(_MAX_CHUNKS)
    )
    chunks = list(chunks_r.scalars().all())
    if not chunks:
        raise ValueError("Knowledge base has no indexed content yet")

    chunk_texts = [c.content for c in chunks]

    # 3. Get homepage URL from first Document in KB with source_url
    doc_r = await db.execute(
        select(Document)
        .where(
            Document.knowledge_base_id == kb_id,
            Document.workspace_id == workspace_id,
            Document.source_url.is_not(None),
        )
        .order_by(Document.created_at.asc())
        .limit(1)
    )
    first_doc = doc_r.scalar_one_or_none()
    homepage_html = ""
    if first_doc and first_doc.source_url:
        try:
            fetch_result = await fetch(first_doc.source_url)
            homepage_html = fetch_result.html
        except Exception as exc:
            logger.warning("Failed to fetch homepage for autoconfig: %s", exc)

    # 4. Generate config
    config = await generate(chunk_texts, homepage_html)

    # 5. Update chatbot fields
    chatbot.name = config.name
    chatbot.welcome_message = config.welcome_message
    chatbot.system_prompt = config.system_prompt
    chatbot.suggested_questions = config.suggested_questions
    chatbot.fallback_message = config.fallback_message
    if config.brand_color is not None:
        chatbot.brand_color = config.brand_color

    await db.commit()
    await db.refresh(chatbot)
    return chatbot
```

- [ ] **Step 2: Verify import**

```bash
docker compose exec backend python -c "from app.services.autoconfig_service import run; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/autoconfig_service.py
git commit -m "feat: add autoconfig_service orchestrator"
```

---

### Task 13: autoconfig endpoint in chatbots.py

**Files:**
- Modify: `backend/app/api/v1/chatbots.py`

- [ ] **Step 1: Update schemas in chatbots schema file**

In `backend/app/schemas/chatbots.py`:

First, add the three new fields to the existing `ChatbotResponse` class so GET /chatbots/{id} returns them after autoconfig runs:
```python
    brand_color: str | None = None
    welcome_message: str | None = None
    suggested_questions: list[str] | None = None
```

Then add at the bottom:

```python
class AutoConfigRequest(BaseModel):
    knowledge_base_id: uuid.UUID


class AutoConfigResponse(BaseModel):
    name: str
    welcome_message: str | None
    system_prompt: str | None
    suggested_questions: list[str] | None
    fallback_message: str | None
    brand_color: str | None
```

- [ ] **Step 2: Add autoconfig endpoint to chatbots.py**

At the end of `backend/app/api/v1/chatbots.py`, add:

```python
from app.schemas.chatbots import AutoConfigRequest, AutoConfigResponse  # add to existing import


@router.post("/{chatbot_id}/autoconfig", response_model=AutoConfigResponse)
async def run_autoconfig(
    chatbot_id: uuid.UUID,
    body: AutoConfigRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    from app.services import autoconfig_service

    try:
        chatbot = await autoconfig_service.run(db, chatbot_id, body.knowledge_base_id, workspace_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

    return AutoConfigResponse(
        name=chatbot.name,
        welcome_message=chatbot.welcome_message,
        system_prompt=chatbot.system_prompt,
        suggested_questions=chatbot.suggested_questions,
        fallback_message=chatbot.fallback_message,
        brand_color=chatbot.brand_color,
    )
```

Note: move the `AutoConfigRequest, AutoConfigResponse` import to the existing import line at the top of the file rather than inside the function.

- [ ] **Step 3: Restart and verify route appears**

```bash
docker compose restart backend
curl -s http://localhost:8000/api/docs | python3 -c "import sys,json; d=json.load(sys.stdin); print([p for p in d['paths'] if 'autoconfig' in p])"
```

Expected: `['/api/v1/workspaces/{workspace_id}/chatbots/{chatbot_id}/autoconfig']`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/chatbots.py backend/app/schemas/chatbots.py
git commit -m "feat: add autoconfig endpoint to chatbots router"
```

---

### Task 14: Integration tests for autoconfig

**Files:**
- Create: `backend/tests/integration/test_autoconfig_api.py`

- [ ] **Step 1: Create integration tests**

```python
# backend/tests/integration/test_autoconfig_api.py
"""Integration tests for POST /chatbots/{id}/autoconfig."""
import pytest
import uuid
from unittest.mock import AsyncMock, patch

from tests.factories import make_chatbot, make_knowledge_base, make_document
from app.services.autoconfig import AutoConfigResult


def _mock_autoconfig_result() -> AutoConfigResult:
    return AutoConfigResult(
        name="Test Bot",
        welcome_message="Hello!",
        system_prompt="You are helpful.",
        suggested_questions=["Q1?", "Q2?", "Q3?", "Q4?"],
        fallback_message="I don't know.",
        brand_color="#4F46E5",
    )


class TestAutoconfigEndpoint:

    async def test_autoconfig_updates_chatbot_fields(self, db, auth_client, workspace):
        bot = await make_chatbot(db, workspace, name="Old Name")
        kb = await make_knowledge_base(db, workspace, bot)

        # Seed a real Document + Chunk so the KB has content
        doc = await make_document(db, workspace, kb, raw_content="We help with product questions.")
        from app.models.knowledge import Chunk
        chunk = Chunk(
            workspace_id=workspace.id,
            document_id=doc.id,
            knowledge_base_id=kb.id,
            chunk_index=0,
            content="We help customers with product questions.",
        )
        db.add(chunk)
        await db.flush()

        with patch("app.services.autoconfig_service.generate", new_callable=AsyncMock) as mock_gen:
            with patch("app.services.autoconfig_service.fetch", new_callable=AsyncMock) as mock_fetch:
                from app.services.fetcher import FetchResult
                mock_fetch.return_value = FetchResult(
                    url="https://a.com", html="<html></html>", text="content",
                    title=None, theme_color=None, status_code=200, used_playwright=False,
                )
                mock_gen.return_value = _mock_autoconfig_result()

                r = await auth_client.post(
                    f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}/autoconfig",
                    json={"knowledge_base_id": str(kb.id)},
                )

        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Test Bot"
        assert data["welcome_message"] == "Hello!"
        assert data["brand_color"] == "#4F46E5"
        assert len(data["suggested_questions"]) == 4

    async def test_autoconfig_returns_422_for_empty_kb(self, db, auth_client, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)

        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}/autoconfig",
            json={"knowledge_base_id": str(kb.id)},
        )
        assert r.status_code == 422
        assert "no indexed content" in r.json()["detail"].lower()

    async def test_autoconfig_returns_404_for_unknown_chatbot(self, auth_client, workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{uuid.uuid4()}/autoconfig",
            json={"knowledge_base_id": str(uuid.uuid4())},
        )
        assert r.status_code == 404

    async def test_autoconfig_tenant_isolation(self, auth_client, second_workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{second_workspace.id}/chatbots/{uuid.uuid4()}/autoconfig",
            json={"knowledge_base_id": str(uuid.uuid4())},
        )
        assert r.status_code == 403
```

- [ ] **Step 2: Run all new tests**

```bash
docker compose exec backend pytest tests/integration/test_autoconfig_api.py -v
```

Expected: all PASS.

- [ ] **Step 3: Run the full test suite to check for regressions**

```bash
make test
```

Expected: all tests pass (or same count as before this feature).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_autoconfig_api.py
git commit -m "test: add autoconfig API integration tests"
```

---

### Task 15: Final smoke test and cleanup

- [ ] **Step 1: Run all backend tests**

```bash
make test
```

Expected: all tests pass.

- [ ] **Step 2: Run unit tests specifically**

```bash
make test-unit
```

Expected: includes `test_fetcher.py`, `test_crawler.py`, `test_autoconfig.py` — all PASS.

- [ ] **Step 3: Run security tests**

```bash
make test-security
```

Expected: all PASS.

- [ ] **Step 4: Verify backend health**

```bash
curl http://localhost:8000/api/v1/health
```

Expected: `{"status":"ok","database":"connected"}`

- [ ] **Step 5: Tag completion commit**

```bash
git commit --allow-empty -m "feat: web crawler and autoconfig complete (P0 items 1+2)"
```
