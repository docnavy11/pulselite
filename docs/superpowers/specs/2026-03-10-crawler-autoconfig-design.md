# Web Crawler & Auto-Configuration Design Spec

**Date:** 2026-03-10
**Scope:** P0 items 1 & 2 from `differences.md` — Web Crawler + Auto-Configuration Service
**Status:** Approved

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
fetcher.py           — pure HTTP: url → content (httpx → Playwright fallback)
crawler.py           — URL discovery: root_url → List[url] (sitemap → BFS fallback)
crawl_service.py     — orchestration: creates KB + Documents + queues ingestion
autoconfig.py        — pure LLM: chunks + html → config dict + brand color
autoconfig_service.py — orchestration: fetches chunks, calls autoconfig, updates Chatbot
crawl_website task   — Celery wrapper for async large-site crawls
```

Existing `ingest_document` Celery task is **unchanged** — crawl_service feeds it pre-fetched Documents.

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

### POST `/api/v1/workspaces/{ws_id}/chatbots/{chatbot_id}/autoconfig`

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

## Component Specifications

### `fetcher.py` — `backend/app/services/fetcher.py`

```python
@dataclass
class FetchResult:
    url: str
    html: str
    text: str
    title: str | None
    theme_color: str | None
    status_code: int
    used_playwright: bool
```

`async fetch(url: str) -> FetchResult`:
- Validate URL scheme (http/https) — raise `ValueError` for others
- httpx GET, timeout=10s, browser-like user-agent
- Extract text via trafilatura (existing pattern from url_extractor.py)
- If `len(text) < 500` → retry with Playwright headless Chromium, `wait_for_load_state("networkidle")`
- Extract `title` from `<title>` tag
- Extract `theme_color` from `<meta name="theme-color">` content attribute
- HTTP errors and timeouts → return `FetchResult(status_code=N, text="", html="", ...)`
- Playwright launch failure → log warning, return httpx result as-is

### `crawler.py` — `backend/app/services/crawler.py`

```python
@dataclass
class CrawlResult:
    urls: list[str]          # truncated to max_pages
    total_discovered: int    # before truncation
    over_limit: bool
    used_sitemap: bool
```

`async discover_urls(root_url: str, max_pages: int) -> CrawlResult`:

**Strategy 1 — Sitemap:**
- Fetch `{root_url}/sitemap.xml` via fetcher
- Parse with `defusedxml` (XXE-safe, existing pattern)
- Recurse into sitemap index files
- Collect all `<loc>` URLs scoped to same domain

**Strategy 2 — BFS fallback** (used when sitemap not found or returns < 3 URLs):
- BFS from root URL, extract `<a href>` links
- Filter: same domain only, no fragments, no query strings on dedup
- Max depth: 3
- `visited` set prevents loops and circular redirects

Both strategies:
- Deduplicate URLs
- Strip fragments (`#anchor`)
- Record `total_discovered` before truncation
- Return `over_limit=True` if `total_discovered > max_pages`

### `crawl_service.py` — `backend/app/services/crawl_service.py`

`async start_crawl(db, workspace_id, url, max_pages, kb_id?) -> CrawlStartResult`:

1. Validate URL scheme
2. Call `crawler.discover_urls(url, max_pages)` → `CrawlResult`
3. Create `KnowledgeBase` if `kb_id` not provided
4. For each URL in `crawl_result.urls`:
   - Call `fetcher.fetch(url)` → `FetchResult`
   - Skip if `status_code >= 400` or `text == ""` (log warning)
   - Create `Document(source_type="url", source_url=url, raw_content=fetch_result.text)`
   - Queue `ingest_document.delay(document.id)`
5. Create `CrawlJob` record tracking progress
6. Return `CrawlStartResult(job_id, kb_id, pages_discovered, pages_queued, over_limit, limit)`

Per-URL failures are logged and skipped — partial crawl is valid.

### `autoconfig.py` — `backend/app/services/autoconfig.py`

`async generate(chunks: list[str], homepage_html: str) -> AutoConfigResult`:

- Sample strategy: first 5 chunks + random sample up to 20 total (diversity)
- Single LLM call (Claude Haiku via existing LLM client), structured JSON output
- Prompt instructs model to generate: `name`, `welcome_message`, `system_prompt` (≤ 300 words), `suggested_questions` (4 items), `fallback_message`
- If LLM returns malformed JSON → retry once with stricter prompt; raise on second failure

`extract_brand_color(html: str) -> str | None`:
- Check `<meta name="theme-color" content="...">` — return if valid hex
- Fallback: scan inline `<style>` for `--primary` CSS variable
- Return `None` if not found (non-fatal)

### `autoconfig_service.py` — `backend/app/services/autoconfig_service.py`

`async run(db, chatbot_id, kb_id, workspace_id) -> Chatbot`:

1. Verify chatbot belongs to workspace (404 if not)
2. Fetch up to 20 chunks from KB (existing vector_store query by `knowledge_base_id`)
3. If zero chunks → raise `ValueError("Knowledge base has no indexed content yet")`
4. Get homepage URL from first Document in KB
5. Fetch homepage HTML via `fetcher.fetch()`
6. Call `autoconfig.generate(chunks, homepage_html)` → `AutoConfigResult`
7. Update Chatbot fields: `name`, `welcome_message`, `system_prompt`, `suggested_questions`, `fallback_message`, `brand_color` (if not None)
8. Return updated Chatbot

### `crawl_website` Celery task — `backend/app/workers/tasks/crawl_website.py`

- Wraps `crawl_service.start_crawl()` via `asyncio.run()` (existing pattern)
- 3 retries, 60s backoff (matches `ingest_document`)
- Updates `CrawlJob.status` on start/complete/failure

---

## Database Changes

### New table: `crawl_jobs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `workspace_id` | UUID FK | |
| `kb_id` | UUID FK | KnowledgeBase |
| `root_url` | TEXT | |
| `status` | ENUM | `pending`, `running`, `completed`, `failed` |
| `pages_discovered` | INT | Before truncation |
| `pages_queued` | INT | |
| `pages_failed` | INT | Default 0 |
| `max_pages` | INT | |
| `over_limit` | BOOL | |
| `created_at` | TIMESTAMP | |
| `completed_at` | TIMESTAMP | Nullable |

### Chatbot model additions

New nullable fields (Alembic migration required):
- `brand_color` — VARCHAR(7), nullable
- `welcome_message` — TEXT, nullable (may already exist — verify)
- `fallback_message` — TEXT, nullable (may already exist — verify)

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Invalid URL scheme | 400 — "URL must be http or https" |
| Sitemap not found / malformed | Fall through to BFS silently |
| BFS finds zero links | Return root URL only (always crawl at least homepage) |
| Per-URL fetch failure | Log + skip, partial crawl succeeds |
| Playwright launch failure | Log warning, return httpx result |
| `max_pages` exceeded | Truncate + `over_limit: true` in response |
| KB has no chunks | 422 — "Knowledge base has no indexed content yet" |
| LLM malformed JSON | Retry once; 500 on second failure |
| Brand color not found | `brand_color: null` — non-fatal |
| Chatbot not in workspace | 404 |
| Cross-workspace access | 403 (existing `get_workspace` dependency) |

---

## Testing

### Unit tests (no DB, no network)
- `test_fetcher.py` — mock httpx; assert Playwright triggered at < 500 chars; assert SSRF guard
- `test_crawler.py` — mock fetcher; sitemap strategy, BFS strategy, dedup, domain scoping, `over_limit`
- `test_autoconfig.py` — fixture chunks + HTML; mock LLM; assert all fields; brand color extraction

### Integration tests (real DB, mocked HTTP)
- `test_crawl_api.py` — mock sitemap + pages; assert Documents created, tasks queued, KB created
- `test_crawl_api.py` — `max_pages` exceeded → `over_limit: true`
- `test_autoconfig_api.py` — seed chunks; mock LLM; assert Chatbot fields updated
- `test_autoconfig_api.py` — empty KB → 422

### Tenant isolation (added to `test_tenant_isolation.py`)
- `POST /workspaces/{other}/crawl` → 403
- `POST /workspaces/{other}/chatbots/{id}/autoconfig` → 403

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
| Create | `backend/app/api/v1/crawl.py` |
| Modify | `backend/app/main.py` — register crawl router |
| Create | `backend/alembic/versions/YYYY_MM_DD_add_crawl_jobs.py` |
| Modify | `backend/app/models/organizational.py` or `knowledge.py` — add CrawlJob model + Chatbot fields |
| Create | `backend/tests/unit/test_fetcher.py` |
| Create | `backend/tests/unit/test_crawler.py` |
| Create | `backend/tests/unit/test_autoconfig.py` |
| Create | `backend/tests/integration/test_crawl_api.py` |
| Create | `backend/tests/integration/test_autoconfig_api.py` |
| Modify | `backend/tests/integration/test_tenant_isolation.py` |
