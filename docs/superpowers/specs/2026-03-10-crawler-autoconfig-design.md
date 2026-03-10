# Web Crawler & Auto-Configuration Design Spec

**Date:** 2026-03-10
**Scope:** P0 items 1 & 2 from `differences.md` — Web Crawler + Auto-Configuration Service
**Status:** Approved (v2 — post-review fixes applied)

---

## Goal

Enable "paste URL → live in 60 seconds" by building:
1. A website crawler that discovers and ingests all pages from a root URL
2. An auto-configuration service that generates chatbot config from crawled content

Both services are fully decoupled and composable. The onboarding wizard (P0.3) will combine them.

---

## Architecture

Full separation of concerns across six components:

```
fetcher.py            — pure HTTP: url → content (httpx → Playwright fallback)
crawler.py            — URL discovery: root_url → List[url] (sitemap → BFS fallback)
crawl_service.py      — orchestration: creates KB + CrawlJob + Documents + queues ingestion
autoconfig.py         — pure LLM: chunks + html → config dict + brand color
autoconfig_service.py — orchestration: fetches chunks, calls autoconfig, updates Chatbot
crawl_website task    — Celery wrapper for async large-site crawls
```

Existing `ingest_document` Celery task is **unchanged** — crawl_service feeds it Documents with `source_type="text"` and `raw_content` pre-populated (skips re-fetch in ingestion pipeline).

---

## API Surface

### POST `/api/v1/workspaces/{ws_id}/crawl`

**Request:**
```json
{
  "url": "https://example.com",
  "max_pages": 50,
  "knowledge_base_id": "optional-uuid"
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "kb_id": "uuid",
  "pages_discovered": 120,
  "pages_queued": 50,
  "over_limit": true,
  "limit": 50
}
```

- `max_pages` is required, must be ≥ 1
- If `knowledge_base_id` omitted, a new KB is created: `"{domain} — crawled {date}"`
- Crawls ≤ 10 pages run synchronously; larger crawls dispatch `crawl_website` Celery task
- URL scheme validated (http/https only — SSRF guard)

### GET `/api/v1/workspaces/{ws_id}/crawl/{job_id}`

**Response:**
```json
{
  "job_id": "uuid",
  "kb_id": "uuid",
  "status": "running",
  "pages_discovered": 120,
  "pages_queued": 50,
  "pages_failed": 2,
  "over_limit": true,
  "limit": 50,
  "created_at": "2026-03-10T10:00:00Z",
  "started_at": "2026-03-10T10:00:01Z",
  "completed_at": null
}
```

- 404 if job not found or not in workspace
- Allows polling until `status` is `completed` or `failed`

### POST `/api/v1/workspaces/{ws_id}/chatbots/{chatbot_id}/autoconfig`

Lives in `backend/app/api/v1/chatbots.py` (appended to existing router).

**Request:**
```json
{
  "knowledge_base_id": "uuid"
}
```

**Response:**
```json
{
  "name": "Acme Support Bot",
  "welcome_message": "Hi! How can I help you today?",
  "system_prompt": "You are a helpful assistant for Acme Corp...",
  "suggested_questions": ["What are your pricing plans?", "..."],
  "fallback_message": "I don't have an answer for that. Want me to connect you with our team?",
  "brand_color": "#4F46E5"
}
```

- Returns 422 if KB has no indexed chunks yet
- `brand_color` is nullable (non-fatal if not found)
- Updates Chatbot record in-place; response reflects updated values

---

## Data Classes

```python
@dataclass
class FetchResult:
    url: str
    html: str           # raw HTML (for color extraction); "" on error
    text: str           # trafilatura-cleaned text; "" on error
    title: str | None
    theme_color: str | None
    status_code: int
    used_playwright: bool

@dataclass
class CrawlResult:
    urls: list[str]          # truncated to max_pages
    total_discovered: int    # before truncation
    over_limit: bool
    used_sitemap: bool

@dataclass
class CrawlStartResult:
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int
    over_limit: bool
    limit: int

@dataclass
class AutoConfigResult:
    name: str
    welcome_message: str
    system_prompt: str
    suggested_questions: list[str]   # 4 items
    fallback_message: str
    brand_color: str | None          # hex "#RRGGBB" or None
```

---

## Component Specifications

### `fetcher.py` — `backend/app/services/fetcher.py`

`async fetch(url: str) -> FetchResult`:
- Validate URL scheme (http/https) — raise `ValueError` for others
- httpx GET, timeout=10s, browser-like user-agent
- Extract text via trafilatura
- If `len(text) < 500` → retry with Playwright headless Chromium, `wait_for_load_state("networkidle")`
- Extract `title` from `<title>` tag
- Extract `theme_color` from `<meta name="theme-color">` content attribute
- HTTP errors and timeouts → return `FetchResult(status_code=N, text="", html="", title=None, theme_color=None, used_playwright=False)`
- Playwright launch failure → log warning, return httpx result as-is

### `crawler.py` — `backend/app/services/crawler.py`

`async discover_urls(root_url: str, max_pages: int) -> CrawlResult`:

**Strategy 1 — Sitemap:**
- Fetch `{root_url}/sitemap.xml` via fetcher
- Parse with `defusedxml` (XXE-safe, existing pattern from `sitemap_extractor.py`)
- Recurse into sitemap index files
- Collect all `<loc>` URLs scoped to same domain

**Strategy 2 — BFS fallback** (used when sitemap returns < 3 URLs or is not found):
- BFS from root URL, extract `<a href>` links
- Filter: same domain only
- **Query string handling:** URLs with query strings are dropped entirely (not just deduped) — parameterised URLs (e.g., `?page=2`, `?sort=price`) rarely contain unique content worth indexing
- Max depth: 3
- `visited` set prevents loops and circular redirects

Both strategies:
- Deduplicate by normalized URL (scheme + host + path, no fragment, no query)
- Record `total_discovered` before truncation to `max_pages`
- Return `over_limit=True` if `total_discovered > max_pages`

### `crawl_service.py` — `backend/app/services/crawl_service.py`

`async start_crawl(db, workspace_id, url, max_pages, kb_id?) -> CrawlStartResult`:

1. Validate URL scheme
2. Call `crawler.discover_urls(url, max_pages)` → `CrawlResult`
3. Create `KnowledgeBase` if `kb_id` not provided
4. Create `CrawlJob` record with `status="pending"` — **commit before queuing any tasks** (`await db.flush()` then `await db.commit()` so Celery workers can read it)
5. Fetch all discovered URLs concurrently: `asyncio.gather(*[fetcher.fetch(u) for u in urls], return_exceptions=True)` with a semaphore of **5 concurrent fetches** to avoid overwhelming targets
6. For each `FetchResult`:
   - Skip if `status_code >= 400` or `text == ""` (log warning, increment `pages_failed`)
   - Create `Document(source_type="text", source_url=url, raw_content=fetch_result.text, title=fetch_result.title)` — **`source_type="text"` ensures ingestion pipeline reads `raw_content` directly without re-fetching**
   - Queue `ingest_document.delay(document.id)`
7. Update `CrawlJob.pages_queued`, `CrawlJob.pages_failed`, `CrawlJob.status="running"`
8. Return `CrawlStartResult`

Per-URL failures are logged and skipped — partial crawl is valid. KB creation failure aborts and raises.

### `autoconfig.py` — `backend/app/services/autoconfig.py`

`async generate(chunks: list[str], homepage_html: str) -> AutoConfigResult`:
- `homepage_html=""` is valid input — `extract_brand_color("")` returns `None` gracefully
- Sample strategy: first 5 chunks + random sample up to 20 total (diversity)
- Single LLM call (Claude Haiku via existing LLM client), structured JSON output
- Prompt instructs model to generate all `AutoConfigResult` fields
- `system_prompt` capped at 300 words, `suggested_questions` exactly 4 items
- If LLM returns malformed JSON → retry once with stricter prompt; raise `RuntimeError` on second failure

`extract_brand_color(html: str) -> str | None`:
- `html=""` → return `None` immediately
- Check `<meta name="theme-color" content="...">` — return if valid hex (`#RRGGBB` or `#RGB`)
- Fallback: scan inline `<style>` for `--primary` CSS variable value
- Return `None` if not found (non-fatal)

### `autoconfig_service.py` — `backend/app/services/autoconfig_service.py`

`async run(db, chatbot_id, kb_id, workspace_id) -> Chatbot`:

1. Verify chatbot belongs to workspace — 404 if not
2. Fetch up to 20 chunks from KB ordered by `chunk_index ASC` (deterministic)
3. If zero chunks → raise `ValueError("Knowledge base has no indexed content yet")`
4. Get homepage URL: query first `Document` in KB ordered by `created_at ASC` where `source_url IS NOT NULL`. If none found, set `homepage_html=""`
5. If homepage URL found: `fetcher.fetch(homepage_url)` → use `fetch_result.html`; on failure `html=""` is passed through
6. Call `autoconfig.generate(chunk_texts, homepage_html)` → `AutoConfigResult`
7. Update Chatbot fields: `name`, `welcome_message`, `system_prompt`, `suggested_questions`, `fallback_message`; update `brand_color` only if not `None`
8. Commit + return updated Chatbot

### `crawl_website` Celery task — `backend/app/workers/tasks/crawl_website.py`

- Wraps `crawl_service.start_crawl()` via `asyncio.run()` (existing pattern)
- On start: update `CrawlJob.status="running"`, `CrawlJob.started_at=now()`
- On complete: update `CrawlJob.status="completed"`, `CrawlJob.completed_at=now()`
- On failure: update `CrawlJob.status="failed"`, `CrawlJob.completed_at=now()`
- 3 retries, 60s backoff (matches `ingest_document`)

---

## Database Changes

### New model: `CrawlJob` — add to `backend/app/models/knowledge.py`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `workspace_id` | UUID FK | workspaces |
| `kb_id` | UUID FK | knowledge_bases |
| `root_url` | TEXT | |
| `status` | ENUM | `pending`, `running`, `completed`, `failed` |
| `pages_discovered` | INT | Before truncation |
| `pages_queued` | INT | Default 0 |
| `pages_failed` | INT | Default 0 |
| `max_pages` | INT | |
| `over_limit` | BOOL | Default false |
| `created_at` | TIMESTAMP | server_default=now() |
| `started_at` | TIMESTAMP | Nullable — set when Celery task begins |
| `completed_at` | TIMESTAMP | Nullable — set on success or failure |

### Chatbot model additions — `backend/app/models/knowledge.py`

New nullable columns requiring Alembic migration:

| Column | Type | Notes |
|--------|------|-------|
| `brand_color` | VARCHAR(7) | Nullable — hex `#RRGGBB` |
| `welcome_message` | TEXT | Nullable — does NOT currently exist |
| `suggested_questions` | JSONB | Nullable — list of strings, does NOT currently exist |

Existing columns **already present** (no migration needed):
- `system_prompt` — TEXT, nullable ✓
- `fallback_message` — TEXT, nullable ✓

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Invalid URL scheme | 400 — "URL must be http or https" |
| `max_pages` < 1 | 400 validation error |
| Sitemap not found / malformed | Fall through to BFS silently |
| BFS finds zero links | Return root URL only (always crawl homepage) |
| Per-URL fetch failure | Log + skip, `pages_failed++`, partial crawl succeeds |
| Playwright launch failure | Log warning, return httpx result |
| `max_pages` exceeded | Truncate + `over_limit: true` in response |
| KB has no chunks | 422 — "Knowledge base has no indexed content yet" |
| No Document with source_url in KB | `homepage_html=""` — proceed without brand color |
| Homepage fetch fails | `html=""` passed to autoconfig — brand color returns `None` |
| LLM malformed JSON | Retry once; `RuntimeError` on second failure → 500 |
| Brand color not found | `brand_color: null` — non-fatal |
| Chatbot not in workspace | 404 |
| Cross-workspace access | 403 (existing `get_workspace` dependency) |

---

## Testing

### Unit tests (no DB, no network)
- `test_fetcher.py` — mock httpx; assert Playwright triggered at < 500 chars; assert SSRF guard; assert empty html on error
- `test_crawler.py` — mock fetcher; sitemap strategy, BFS strategy, dedup, domain scoping, query-string dropping, `over_limit`
- `test_autoconfig.py` — fixture chunks + HTML; mock LLM; assert all fields; brand color extraction; `homepage_html=""` returns `brand_color=None`

### Integration tests (real DB, mocked HTTP)
- `test_crawl_api.py` — mock sitemap + pages; assert Documents created with `source_type="text"`, tasks queued, KB created, CrawlJob row present
- `test_crawl_api.py` — `max_pages` exceeded → `over_limit: true`
- `test_crawl_api.py` — `GET /crawl/{job_id}` returns correct status
- `test_autoconfig_api.py` — seed chunks; mock LLM; assert Chatbot fields updated
- `test_autoconfig_api.py` — empty KB → 422

### Tenant isolation (added to `test_tenant_isolation.py`)
- `POST /workspaces/{other}/crawl` → 403
- `POST /workspaces/{other}/chatbots/{id}/autoconfig` → 403
- `GET /workspaces/{other}/crawl/{job_id}` → 403

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/app/services/fetcher.py` |
| Create | `backend/app/services/crawler.py` |
| Create | `backend/app/services/crawl_service.py` |
| Create | `backend/app/services/autoconfig.py` |
| Create | `backend/app/services/autoconfig_service.py` |
| Create | `backend/app/workers/tasks/crawl_website.py` |
| Create | `backend/app/api/v1/crawl.py` — POST /crawl + GET /crawl/{job_id} |
| Modify | `backend/app/api/v1/chatbots.py` — add POST /chatbots/{id}/autoconfig |
| Modify | `backend/app/main.py` — register crawl router |
| Modify | `backend/app/models/knowledge.py` — add CrawlJob model + Chatbot fields |
| Create | `backend/alembic/versions/YYYY_MM_DD_add_crawl_jobs_and_chatbot_fields.py` |
| Create | `backend/tests/unit/test_fetcher.py` |
| Create | `backend/tests/unit/test_crawler.py` |
| Create | `backend/tests/unit/test_autoconfig.py` |
| Create | `backend/tests/integration/test_crawl_api.py` |
| Create | `backend/tests/integration/test_autoconfig_api.py` |
| Modify | `backend/tests/integration/test_tenant_isolation.py` |
