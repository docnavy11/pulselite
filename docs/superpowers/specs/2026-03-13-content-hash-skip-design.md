# Content Hash Skip — Design Spec

## Goal

Skip re-ingestion during periodic sync when document content hasn't changed, saving embedding API credits and CPU.

## Problem

`sync_stale_documents` fires `ingest_document` for every due document. The pipeline always runs the full extract → chunk → embed → store cycle, even when content is identical to the last run. There is no content change detection.

## Solution

Add a `content_hash` column (SHA-256) to Document. After extracting content, compare the hash with the stored value. If identical, update `last_indexed_at` and return early — skip chunking, embedding, and indexing.

## Database

New column on `documents` table:

```
content_hash  String(64)  nullable  default NULL
```

- SHA-256 hex digest of extracted content (always exactly 64 chars)
- `NULL` for existing documents — first sync populates it
- Migration: add column only, no backfill needed

## Pipeline Change

**File:** `backend/app/services/ingestion/pipeline.py`, in `run_ingestion()`

**Placement:** After `_record("extract", ...)` and before the character budget enforcement block. Add `import hashlib` at the top of the file.

1. Compute `new_hash = hashlib.sha256(content.encode()).hexdigest()`
2. If `document.content_hash == new_hash`:
   - Record step via `_record("hash_check", "skipped", t0, detail="content unchanged")`
   - Set `document.status = "indexed"`
   - Set `document.error_message = None` (clear any previous failure)
   - Set `document.last_indexed_at = now`
   - Set `document.ingestion_steps = steps`
   - `await db.flush()` and return early (matches existing pattern — `commit()` happens in the calling task)
   - Log: `logger.info("Document %s: content unchanged, skipping re-ingestion", document_id)`
3. Else:
   - Set `document.content_hash = new_hash`
   - Continue with the existing pipeline (budget check → chunk → embed → index)

### Why before budget check

If content is unchanged, there's no reason to debit the character budget. The budget was already debited on initial ingestion.

**Note on budget for changed content:** When content *does* change during re-sync, the budget check adds the new `char_count` without subtracting the old value. This is pre-existing behavior, not introduced by this feature. Addressing it is out of scope.

### Hash on full extracted content, not raw_content

URL sources re-fetch the page — `_extract()` returns fresh content. Text sources return `raw_content` as-is. The hash is always computed on the `_extract()` output, which is the canonical content that gets chunked.

## Status lifecycle with sync

The sync flow is: `sync_stale_documents` sets `status = "stale"` → `ingest_document` fires → idempotency guard (checks for `"indexed"/"skipped"`) passes since status is `"stale"` → `run_ingestion()` runs → hash check sets status back to `"indexed"` if content unchanged. This is compatible — the `"stale"` status ensures the pipeline runs, and the hash check short-circuits the expensive work.

## What changes on first ingestion

On first ingestion (or any ingestion where `content_hash` is `NULL`), the hash check is a no-op — `NULL != new_hash` is always true in Python. The hash is stored for future comparison.

## Extraction failure

If `_extract()` raises an exception (e.g. page is down), the document is marked `"failed"` as before. The hash check is never reached. The old `content_hash` is preserved and will be compared on the next successful extraction.

## Affected source types

The hash check applies to the **standard path only** (url, file, text, qa) — the code path that calls `_extract()`. Special source types (sitemap, notion, google_drive, dropbox, salesforce, zendesk) have their own extraction logic and are out of scope for this change.

## No frontend changes

The existing UI already displays `last_indexed_at` and `ingestion_steps`. The new "hash_check" step will appear naturally in the document detail panel.

## Testing

### Backend tests
- Test: unchanged content skips re-ingestion (hash matches → status "indexed", no new chunks created, `chars_indexed` not incremented)
- Test: changed content triggers full re-ingestion (hash differs → new chunks, new hash stored)
- Test: first ingestion with NULL hash proceeds normally and stores hash
- Test: hash_check step appears in ingestion_steps when skipped
- Test: empty content string produces a valid hash and does not cause false skip
