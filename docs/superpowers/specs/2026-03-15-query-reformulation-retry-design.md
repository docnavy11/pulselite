# Query Reformulation Retry on Low Confidence — Design Spec

## Overview

When the RAG pipeline's initial retrieval scores below `chatbot.confidence_threshold`, instead of immediately escalating, the system asks the LLM to rephrase the query 3 ways, re-runs retrieval for each, and uses the best chunks to generate the response. One retry round only — no recursive loops.

Gap events are always recorded when the original query had low confidence, regardless of whether the retry improved things. This preserves KB gap detection for the intelligence pipeline.

## Current Behavior

1. Hybrid search (dense + sparse via RRF) → scored chunks
2. `compute_confidence` → `should_escalate` check
3. If low confidence → `RAGResult(escalated=True)` → LLM still generates a response → conversation marked as escalated, gap event recorded

## New Behavior

1. Hybrid search → scored chunks → confidence check
2. If confidence >= threshold → proceed as today (no change)
3. If confidence < threshold:
   a. Call LLM with reformulation prompt → 3 alternative queries (JSON)
   b. Run `hybrid_search` for each of the 3 queries (sequential — `AsyncSession` is not concurrent-safe)
   c. Merge all chunks (original + retry), deduplicate by chunk ID
   d. **Always rerank** the merged set via CrossEncoder (regardless of `chatbot.use_reranking`) — this is required because without reranking, merged chunks have no meaningful scores and confidence cannot improve
   e. Recompute confidence on the reranked set
   f. If new confidence >= threshold → `escalated=False`
   g. If still below → `escalated=True` (best-effort answer with merged chunks)
4. Gap event recorded whenever the **original** query had low confidence — not gated on final `escalated` flag

## File Changes

### New file: `backend/app/services/rag/reformulator.py`

Single function:

```python
async def reformulate_queries(
    query: str,
    chatbot: Chatbot,
    openrouter_key: str | None = None,
    openrouter_base_url: str | None = None,
) -> list[str]:
```

- Calls LLM via `get_llm_client()` with a short system prompt asking for 3 rephrased queries
- Parses JSON response: `{"queries": ["...", "...", "..."]}`
- Returns the list of query strings
- On any error (LLM failure, bad JSON, timeout), logs a warning and returns an empty list

LLM call details:
- Provider/key: same logic as `generator.py` — use workspace OpenRouter key if available, else chatbot's provider. BYOK key decryption handled the same way (import `decrypt_api_key` from `app.services.encryption` when `chatbot.byoak` is set and no workspace key exists).
- Model: `chatbot.llm_model`
- Temperature: 0.7 (diversity in rephrasing)
- Max tokens: 200
- System prompt: `"You are a search query optimizer. Given a user question, generate 3 alternative phrasings that might match different content in a knowledge base. Return JSON only: {\"queries\": [\"...\", \"...\", \"...\"]}"`
- If the LLM returns fewer than 3 queries, use whatever is returned (1 or 2 is still useful). If it returns 0 or an empty list, treat as failure and fall back to original chunks.

### Modified: `backend/app/services/rag/engine.py`

In `process_query`, after the initial confidence check:

```python
original_confidence_low = should_escalate(confidence_score, chatbot.confidence_threshold)

if original_confidence_low:
    retry_queries = await reformulate_queries(query, chatbot, openrouter_key, openrouter_base_url)
    if retry_queries:
        # Run hybrid search for each reformulated query
        all_chunks = list(candidates)  # start with originals
        seen_ids = {c.id for c in candidates}
        for rq in retry_queries:
            new_candidates = await hybrid_search(db, chatbot.workspace_id, kb.id, rq, top_k=20)
            for c in new_candidates:
                if c.id not in seen_ids:
                    all_chunks.append(c)
                    seen_ids.add(c.id)

        # Always rerank on retry path — without reranking, merged chunks
        # have no meaningful scores and confidence can never improve
        if all_chunks:
            scored_chunks = rerank(query, all_chunks, top_k=chatbot.retrieval_top_k)

        confidence_score, confidence_avg = compute_confidence(scored_chunks)
        escalated = should_escalate(confidence_score, chatbot.confidence_threshold)
        retrieved_chunk_ids = [chunk.id for chunk, _ in scored_chunks]
```

`RAGResult` gets two new fields:
- `retried: bool = False` — whether the reformulation retry was attempted
- `original_confidence_low: bool = False` — whether the original query had low confidence (drives gap event recording)

The early-return path (no KB found, line 42-51) needs no changes — the new fields default to `False`, which is correct for that case.

### Modified: `backend/app/services/resolution_service.py`

One change — gap event condition (line 223):

Before:
```python
if escalated and _is_substantive_query(message):
```

After:
```python
if rag_result.original_confidence_low and _is_substantive_query(message):
```

This records gap events whenever the original retrieval was weak, even if retry improved confidence above threshold.

## What Doesn't Change

- `resolution_service.py` flow — still reads `escalated` from `RAGResult` for conversation escalation logic
- `backend/app/services/rag/confidence.py`, `backend/app/services/rag/retriever.py`, `backend/app/services/rag/memory.py`, `backend/app/services/rag/generator.py`, `backend/app/services/rag/prompts.py` — untouched
- `backend/app/services/rag/reranker.py` — untouched (called on the retry path, but no code changes needed)
- Frontend — no changes, same SSE stream
- Database schema — no migrations needed
- Escalation webhook — still fires only when final `escalated=True`

## Error Handling

- LLM reformulation fails → log warning, proceed with original chunks (same as today's behavior)
- Bad JSON from LLM → catch, log, return empty list → no retry, original path
- Individual retry hybrid_search fails → skip that query, continue with others

The retry is best-effort. It never blocks or breaks the response pipeline.

## Performance

Added latency on the low-confidence path only:
- ~0.5-1s for the reformulation LLM call (small prompt, 200 max tokens)
- ~1.5-3s for 3 sequential hybrid searches (each involves an embedding call + 2 DB queries; sequential because `AsyncSession` is not concurrent-safe)
- ~0.5s for CrossEncoder reranking on merged set
- Total: ~2.5-4.5s extra, acceptable since the alternative was escalation (no useful answer)

No impact on queries above the confidence threshold. Parallelizing the hybrid searches would require separate DB sessions — a potential future optimization.

## Testing

- `test_rag_reformulator.py` — test LLM prompt construction, JSON parsing, error fallback
- `test_rag_engine.py` — extend with retry path tests: low confidence triggers retry, merged chunks used, confidence recomputed
- `test_resolution_service.py` — extend: gap event recorded when `original_confidence_low=True` even if `escalated=False`
