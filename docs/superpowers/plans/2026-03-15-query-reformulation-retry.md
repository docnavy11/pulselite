# Query Reformulation Retry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When RAG confidence is low, use LLM to rephrase the query 3 ways, re-retrieve, rerank the merged chunks, and generate a better answer before escalating.

**Architecture:** New `reformulator.py` module handles the LLM call + JSON parsing. `engine.py` orchestrates the retry loop (search → merge → rerank → recompute confidence). `resolution_service.py` gets a one-line gap event condition change. TDD throughout.

**Tech Stack:** Python, pytest, pytest-asyncio, unittest.mock

**Spec:** `docs/superpowers/specs/2026-03-15-query-reformulation-retry-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/services/rag/reformulator.py` | Create | LLM call to generate 3 rephrased queries, JSON parsing, error handling |
| `backend/app/services/rag/engine.py` | Modify | Add retry logic after initial confidence check, add `retried` and `original_confidence_low` fields to `RAGResult` |
| `backend/app/services/resolution_service.py` | Modify | Change gap event condition from `escalated` to `rag_result.original_confidence_low` |
| `backend/tests/unit/test_rag_reformulator.py` | Create | Tests for `reformulate_queries` |
| `backend/tests/unit/test_rag_engine.py` | Modify | Add retry path tests |
| `backend/tests/unit/test_resolution_service.py` | Modify | Add gap event with `original_confidence_low` tests |

---

## Chunk 1: Reformulator Module

### Task 1: Create reformulator with tests

**Files:**
- Create: `backend/tests/unit/test_rag_reformulator.py`
- Create: `backend/app/services/rag/reformulator.py`

- [ ] **Step 1: Write the reformulator tests**

```python
# backend/tests/unit/test_rag_reformulator.py
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.id = "cb-1"
    cb.llm_provider = overrides.get("llm_provider", "openrouter")
    cb.llm_model = overrides.get("llm_model", "openai/gpt-4o-mini")
    cb.byoak = overrides.get("byoak", None)
    cb.workspace_id = "ws-1"
    return cb


class TestReformulateQueries:
    @pytest.mark.asyncio
    async def test_returns_three_queries_on_success(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value=json.dumps({
            "queries": [
                "How to set up SSO?",
                "SAML configuration guide",
                "Single sign-on setup steps",
            ]
        }))

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries(
                "How do I configure SAML SSO?",
                _make_chatbot(),
            )

        assert len(result) == 3
        assert "SSO" in result[0]
        mock_client.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_workspace_openrouter_key(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1", "q2", "q3"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client) as mock_get:
            await reformulate_queries(
                "test query",
                _make_chatbot(),
                openrouter_key="sk-ws-key",
            )

        mock_get.assert_called_once_with("openrouter", api_key="sk-ws-key", base_url=None)

    @pytest.mark.asyncio
    async def test_uses_byoak_when_no_workspace_key(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1", "q2", "q3"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client) as mock_get, \
             patch("app.services.encryption.decrypt_api_key", return_value="decrypted-key"):
            await reformulate_queries(
                "test query",
                _make_chatbot(byoak="encrypted-key", llm_provider="openai"),
            )

        mock_get.assert_called_once_with("openai", api_key="decrypted-key", base_url=None)

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_llm_error(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(side_effect=Exception("LLM timeout"))

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_invalid_json(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value="not json at all")

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_missing_queries_key(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"rephrased": ["q1"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_fewer_than_three_queries(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            result = await reformulate_queries("test", _make_chatbot())

        assert result == ["q1"]

    @pytest.mark.asyncio
    async def test_system_prompt_includes_optimization_instruction(self):
        from app.services.rag.reformulator import reformulate_queries

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"queries": ["q1", "q2", "q3"]}')

        with patch("app.services.rag.reformulator.get_llm_client", return_value=mock_client):
            await reformulate_queries("How do I login?", _make_chatbot())

        call_kwargs = mock_client.generate.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages") or call_kwargs[0][0]
        system_msg = [m for m in messages if m["role"] == "system"][0]
        assert "alternative" in system_msg["content"].lower() or "rephras" in system_msg["content"].lower()
        user_msg = [m for m in messages if m["role"] == "user"][0]
        assert "How do I login?" in user_msg["content"]
```

- [ ] **Step 2: Run tests — expect failures (module doesn't exist)**

Run: `docker compose exec backend pytest tests/unit/test_rag_reformulator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.rag.reformulator'`

- [ ] **Step 3: Write the reformulator implementation**

```python
# backend/app/services/rag/reformulator.py
import json
import logging

from app.models.knowledge import Chatbot
from app.services.llm import get_llm_client

logger = logging.getLogger(__name__)

REFORMULATION_SYSTEM_PROMPT = (
    "You are a search query optimizer. Given a user question, generate 3 alternative phrasings "
    "that might match different content in a knowledge base. Return JSON only: "
    '{"queries": ["...", "...", "..."]}'
)


async def reformulate_queries(
    query: str,
    chatbot: Chatbot,
    openrouter_key: str | None = None,
    openrouter_base_url: str | None = None,
) -> list[str]:
    """Ask the LLM to rephrase the query 3 ways for better retrieval.

    Returns a list of rephrased queries, or an empty list on any error.
    """
    try:
        api_key = openrouter_key
        if api_key is None and chatbot.byoak:
            from app.services.encryption import decrypt_api_key
            api_key = decrypt_api_key(chatbot.byoak)

        provider = "openrouter" if openrouter_key else chatbot.llm_provider
        client = get_llm_client(provider, api_key=api_key, base_url=openrouter_base_url)

        response = await client.generate(
            messages=[
                {"role": "system", "content": REFORMULATION_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            model=chatbot.llm_model,
            temperature=0.7,
            max_tokens=200,
        )

        data = json.loads(response)
        queries = data.get("queries", [])
        if not isinstance(queries, list) or len(queries) == 0:
            logger.warning(f"Reformulation returned no queries for: {query[:80]}")
            return []
        return [q for q in queries if isinstance(q, str) and q.strip()]

    except Exception:
        logger.warning(f"Query reformulation failed for: {query[:80]}", exc_info=True)
        return []
```

- [ ] **Step 4: Run tests — expect all 8 pass**

Run: `docker compose exec backend pytest tests/unit/test_rag_reformulator.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/rag/reformulator.py backend/tests/unit/test_rag_reformulator.py
git commit -m "feat: add query reformulation module with LLM-based rephrasing

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 2: Engine Retry Logic + RAGResult Fields

### Task 2: Add new fields to RAGResult and retry logic in engine.py

**Files:**
- Modify: `backend/app/services/rag/engine.py:20-27` (RAGResult dataclass)
- Modify: `backend/app/services/rag/engine.py:53-63` (after hybrid_search, add retry block)
- Modify: `backend/tests/unit/test_rag_engine.py` (add retry tests)

- [ ] **Step 1: Write the retry path tests**

Append to `backend/tests/unit/test_rag_engine.py`:

```python
# --- Add these tests to the existing TestProcessQuery class ---

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_retry(self):
        """When initial confidence is below threshold, reformulate + re-search + rerank."""
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        original_chunk = _make_chunk("orig")
        retry_chunk = _make_chunk("retry", content="better content")

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        # First hybrid_search returns original chunk, retry searches return new chunk
        search_calls = [
            [original_chunk],         # original search
            [retry_chunk],            # reformulated query 1
            [],                       # reformulated query 2
            [],                       # reformulated query 3
        ]
        search_call_idx = {"i": 0}

        async def mock_hybrid_search(*args, **kwargs):
            idx = search_call_idx["i"]
            search_call_idx["i"] += 1
            return search_calls[idx]

        async def fake_stream(*args, **kwargs):
            yield "answer"

        with patch("app.services.rag.engine.hybrid_search", side_effect=mock_hybrid_search), \
             patch("app.services.rag.engine.compute_confidence") as mock_conf, \
             patch("app.services.rag.engine.should_escalate") as mock_esc, \
             patch("app.services.rag.engine.rerank", return_value=[(retry_chunk, 0.85), (original_chunk, 0.4)]) as mock_rerank, \
             patch("app.services.rag.engine.reformulate_queries", new_callable=AsyncMock, return_value=["q1", "q2", "q3"]), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            # First confidence check: low → triggers retry
            # Second confidence check (after retry): high
            mock_conf.side_effect = [(0.2, 0.2), (0.85, 0.6)]
            mock_esc.side_effect = [True, False]

            items = []
            async for item in process_query(db, "test query", _make_chatbot()):
                items.append(item)

        # Rerank was called on merged chunks (always reranks on retry)
        mock_rerank.assert_called_once()
        # RAGResult should reflect retry success
        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert rag_results[0].retried is True
        assert rag_results[0].original_confidence_low is True
        assert rag_results[0].escalated is False

    @pytest.mark.asyncio
    async def test_retry_still_escalates_when_confidence_stays_low(self):
        """When retry doesn't improve confidence, still escalates."""
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        chunk = _make_chunk("c1")

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        async def mock_hybrid_search(*args, **kwargs):
            return [chunk]

        async def fake_stream(*args, **kwargs):
            yield "fallback answer"

        with patch("app.services.rag.engine.hybrid_search", side_effect=mock_hybrid_search), \
             patch("app.services.rag.engine.compute_confidence", return_value=(0.2, 0.2)), \
             patch("app.services.rag.engine.should_escalate", return_value=True), \
             patch("app.services.rag.engine.rerank", return_value=[(chunk, 0.15)]), \
             patch("app.services.rag.engine.reformulate_queries", new_callable=AsyncMock, return_value=["q1", "q2", "q3"]), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            items = []
            async for item in process_query(db, "test", _make_chatbot()):
                items.append(item)

        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert rag_results[0].retried is True
        assert rag_results[0].original_confidence_low is True
        assert rag_results[0].escalated is True

    @pytest.mark.asyncio
    async def test_reformulation_failure_proceeds_without_retry(self):
        """When reformulate_queries returns empty list, no retry happens."""
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        chunk = _make_chunk("c1")

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        async def fake_stream(*args, **kwargs):
            yield "answer"

        with patch("app.services.rag.engine.hybrid_search", new_callable=AsyncMock, return_value=[chunk]), \
             patch("app.services.rag.engine.compute_confidence", return_value=(0.2, 0.2)), \
             patch("app.services.rag.engine.should_escalate", return_value=True), \
             patch("app.services.rag.engine.reformulate_queries", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            items = []
            async for item in process_query(db, "test", _make_chatbot()):
                items.append(item)

        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert rag_results[0].retried is False
        assert rag_results[0].original_confidence_low is True
        assert rag_results[0].escalated is True

    @pytest.mark.asyncio
    async def test_retry_deduplicates_chunks(self):
        """Chunks appearing in multiple search results are not duplicated."""
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        shared_chunk = _make_chunk("shared")
        unique_chunk = _make_chunk("unique")

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        search_calls = [
            [shared_chunk],                   # original
            [shared_chunk, unique_chunk],      # retry query 1 (shared appears again)
        ]
        search_call_idx = {"i": 0}

        async def mock_hybrid_search(*args, **kwargs):
            idx = search_call_idx["i"]
            search_call_idx["i"] += 1
            return search_calls[idx] if idx < len(search_calls) else []

        async def fake_stream(*args, **kwargs):
            yield "answer"

        with patch("app.services.rag.engine.hybrid_search", side_effect=mock_hybrid_search), \
             patch("app.services.rag.engine.compute_confidence") as mock_conf, \
             patch("app.services.rag.engine.should_escalate") as mock_esc, \
             patch("app.services.rag.engine.rerank") as mock_rerank, \
             patch("app.services.rag.engine.reformulate_queries", new_callable=AsyncMock, return_value=["q1"]), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            mock_conf.side_effect = [(0.2, 0.2), (0.8, 0.8)]
            mock_esc.side_effect = [True, False]
            mock_rerank.return_value = [(shared_chunk, 0.9), (unique_chunk, 0.7)]

            items = []
            async for item in process_query(db, "test", _make_chatbot()):
                items.append(item)

        # rerank should receive exactly 2 chunks (deduplicated), not 3
        rerank_call_chunks = mock_rerank.call_args[0][1]
        chunk_ids = [c.id for c in rerank_call_chunks]
        assert len(chunk_ids) == 2
        assert "shared" in chunk_ids
        assert "unique" in chunk_ids
```

- [ ] **Step 2: Run tests — expect failures (retry logic not implemented)**

Run: `docker compose exec backend pytest tests/unit/test_rag_engine.py -v`
Expected: 3 existing PASS, 4 new FAIL

- [ ] **Step 3: Modify RAGResult dataclass**

In `backend/app/services/rag/engine.py`, change the `RAGResult` dataclass (lines 20-27) to:

```python
@dataclass
class RAGResult:
    confidence_score: float
    confidence_avg: float
    escalated: bool
    retrieved_chunk_ids: list[uuid.UUID]
    query: str
    sources: list[dict] = field(default_factory=list)
    retried: bool = False
    original_confidence_low: bool = False
```

- [ ] **Step 4: Add retry logic to process_query**

In `backend/app/services/rag/engine.py`, add the import at the top (after existing imports):

```python
from app.services.rag.reformulator import reformulate_queries
```

Then replace lines 53-63 (from `candidates = await hybrid_search(...)` through `retrieved_chunk_ids = ...`) with:

```python
    candidates = await hybrid_search(db, chatbot.workspace_id, kb.id, query, top_k=20)

    if chatbot.use_reranking and candidates:
        scored_chunks = rerank(query, candidates, top_k=chatbot.retrieval_top_k)
    else:
        scored_chunks = [(c, 0.5) for c in candidates[: chatbot.retrieval_top_k]]

    confidence_score, confidence_avg = compute_confidence(scored_chunks)
    escalated = should_escalate(confidence_score, chatbot.confidence_threshold)
    original_confidence_low = escalated
    retried = False

    # --- Query reformulation retry on low confidence ---
    if original_confidence_low:
        retry_queries = await reformulate_queries(query, chatbot, openrouter_key, openrouter_base_url)
        if retry_queries:
            retried = True
            all_chunks = list(candidates)
            seen_ids = {c.id for c in candidates}
            for rq in retry_queries:
                new_candidates = await hybrid_search(db, chatbot.workspace_id, kb.id, rq, top_k=20)
                for c in new_candidates:
                    if c.id not in seen_ids:
                        all_chunks.append(c)
                        seen_ids.add(c.id)

            # Always rerank on retry — without meaningful scores, confidence can't improve
            if all_chunks:
                scored_chunks = rerank(query, all_chunks, top_k=chatbot.retrieval_top_k)
                confidence_score, confidence_avg = compute_confidence(scored_chunks)
                escalated = should_escalate(confidence_score, chatbot.confidence_threshold)

    retrieved_chunk_ids = [chunk.id for chunk, _ in scored_chunks]
```

And update the RAGResult construction (around line 88) to include the new fields:

```python
    rag_result = RAGResult(
        confidence_score=confidence_score,
        confidence_avg=confidence_avg,
        escalated=escalated,
        retrieved_chunk_ids=retrieved_chunk_ids,
        query=query,
        sources=sources,
        retried=retried,
        original_confidence_low=original_confidence_low,
    )
```

- [ ] **Step 5: Run tests — expect all pass (3 existing + 4 new)**

Run: `docker compose exec backend pytest tests/unit/test_rag_engine.py -v`
Expected: 7 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/rag/engine.py backend/tests/unit/test_rag_engine.py
git commit -m "feat: add query reformulation retry on low confidence in RAG engine

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 3: Resolution Service Gap Event Change

### Task 3: Update gap event condition in resolution_service.py

**Files:**
- Modify: `backend/app/services/resolution_service.py:223`
- Modify: `backend/tests/unit/test_resolution_service.py` (add tests)

- [ ] **Step 1: Write the gap event tests**

Append to `backend/tests/unit/test_resolution_service.py` (inside the existing `TestHandleMessage` class):

```python
    @pytest.mark.asyncio
    async def test_gap_event_recorded_when_original_confidence_low_even_if_retry_succeeds(self):
        """Gap event should be recorded based on original_confidence_low, not escalated."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        user_message = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        # Retry succeeded: escalated=False but original_confidence_low=True
        rag_result = RAGResult(
            confidence_score=0.8, confidence_avg=0.7, escalated=False,
            retrieved_chunk_ids=[], query="How do I configure SAML SSO?",
            sources=[], retried=True, original_confidence_low=True,
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Here's how to configure SAML SSO..."
            yield {"prompt_tokens": 50, "completion_tokens": 20}

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "How do I configure SAML SSO?")
            )

        # Gap event should be recorded (db.add called with GapEvent)
        add_calls = db.add.call_args_list
        from app.models.intelligence import GapEvent as GapEventModel
        gap_adds = [c for c in add_calls if isinstance(c[0][0], GapEventModel)]
        assert len(gap_adds) == 1

    @pytest.mark.asyncio
    async def test_no_gap_event_when_original_confidence_was_fine(self):
        """No gap event when original confidence was above threshold (no retry needed)."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        conversation.escalation_reason = None
        conversation.outcome = None
        conversation.confidence_avg = None
        conversation.ai_participated = False
        conversation.autonomous_resolved = False
        user_message = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.9, confidence_avg=0.8, escalated=False,
            retrieved_chunk_ids=[], query="What are your pricing plans?",
            sources=[], retried=False, original_confidence_low=False,
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Our pricing plans are..."
            yield {"prompt_tokens": 30, "completion_tokens": 15}

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.resolution_service.is_cloud", return_value=False), \
             patch("app.services.resolution_service.conversation_service") as mock_conv, \
             patch("app.services.resolution_service.process_query", side_effect=fake_process_query), \
             patch("app.services.resolution_service.fire_event", new_callable=AsyncMock), \
             patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.action_executor.run_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(side_effect=[user_message, bot_message])

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "What are your pricing plans?")
            )

        # No gap event should be recorded
        add_calls = db.add.call_args_list
        from app.models.intelligence import GapEvent as GapEventModel
        gap_adds = [c for c in add_calls if isinstance(c[0][0], GapEventModel)]
        assert len(gap_adds) == 0
```

- [ ] **Step 2: Run tests — expect the new gap event test to fail**

Run: `docker compose exec backend pytest tests/unit/test_resolution_service.py::TestHandleMessage::test_gap_event_recorded_when_original_confidence_low_even_if_retry_succeeds -v`
Expected: FAIL (current code checks `escalated`, not `original_confidence_low`)

- [ ] **Step 3: Update gap event condition**

In `backend/app/services/resolution_service.py`, change line 223 from:

```python
        if escalated and _is_substantive_query(message):
```

to:

```python
        if rag_result and rag_result.original_confidence_low and _is_substantive_query(message):
```

- [ ] **Step 4: Run all resolution service tests**

Run: `docker compose exec backend pytest tests/unit/test_resolution_service.py -v`
Expected: 13 PASSED (7 substantive + 4 handle_message + 2 new gap event)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/resolution_service.py backend/tests/unit/test_resolution_service.py
git commit -m "feat: record gap events based on original confidence, not final escalation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Final verification

- [ ] **Step 1: Run full backend unit test suite**

Run: `docker compose exec backend pytest tests/unit/ -v --tb=short`
Expected: All tests pass (307 existing + ~14 new = ~321)

- [ ] **Step 2: Run targeted coverage**

Run: `docker compose exec backend pytest tests/unit/ --cov=app/services/rag --cov-report=term-missing --tb=short`
Expected: `reformulator.py` at high coverage, `engine.py` coverage improved

- [ ] **Step 3: Commit any fixes if needed**
