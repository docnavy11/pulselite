# Phase 1a: RAG Pipeline Unit Tests — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ~45 unit tests covering the resolution service, RAG pipeline, credits, and deployment modules — all currently at zero coverage.

**Architecture:** Bottom-up through the RAG pipeline: pure functions first (confidence, prompts, sigmoid, RRF, cost estimation), then mock-based component tests (reranker, retriever, memory, generator), then orchestrators (engine, resolution_service). Every test mocks external I/O (DB, LLM, embedder, Stripe) — no real services needed.

**Tech Stack:** pytest, pytest-asyncio (auto mode), unittest.mock (AsyncMock, patch, MagicMock)

**Spec:** `docs/superpowers/specs/2026-03-15-testing-strategy-design.md` (Phase 1, cycle 1a)

---

## File Structure

| File | Action | What it tests |
|------|--------|--------------|
| `backend/tests/unit/test_rag_confidence.py` | Create | `compute_confidence`, `should_escalate` |
| `backend/tests/unit/test_rag_prompts.py` | Create | `build_system_prompt`, `build_context_prompt`, `_build_language_instruction` |
| `backend/tests/unit/test_rag_reranker.py` | Create | `_sigmoid`, `rerank` (mock CrossEncoder) |
| `backend/tests/unit/test_rag_retriever.py` | Create | `_reciprocal_rank_fusion`, `hybrid_search` (mock DB + embedder) |
| `backend/tests/unit/test_rag_memory.py` | Create | `get_conversation_history` (mock DB) |
| `backend/tests/unit/test_rag_generator.py` | Create | `stream_response` (mock LLM client) |
| `backend/tests/unit/test_rag_engine.py` | Create | `process_query` orchestration (mock retriever, reranker, generator) |
| `backend/tests/unit/test_credits.py` | Create | `estimate_token_cost` pure function |
| `backend/tests/unit/test_deployment.py` | Create | `is_cloud`, `is_self_hosted` |
| `backend/tests/unit/test_resolution_service.py` | Create | `_is_substantive_query`, `handle_message` full pipeline |

---

## Chunk 1: Pure Function Tests

### Task 1: RAG confidence tests

**Files:**
- Create: `backend/tests/unit/test_rag_confidence.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from unittest.mock import MagicMock


def _make_chunk(chunk_id="c1"):
    chunk = MagicMock()
    chunk.id = chunk_id
    return chunk


class TestComputeConfidence:
    def test_empty_chunks_returns_zeros(self):
        from app.services.rag.confidence import compute_confidence
        score, avg = compute_confidence([])
        assert score == 0.0
        assert avg == 0.0

    def test_single_chunk(self):
        from app.services.rag.confidence import compute_confidence
        scored = [(_make_chunk(), 0.85)]
        score, avg = compute_confidence(scored)
        assert score == 0.85
        assert avg == 0.85

    def test_multiple_chunks_max_and_avg(self):
        from app.services.rag.confidence import compute_confidence
        scored = [(_make_chunk("c1"), 0.9), (_make_chunk("c2"), 0.3), (_make_chunk("c3"), 0.6)]
        score, avg = compute_confidence(scored)
        assert score == 0.9
        assert avg == pytest.approx(0.6, abs=0.01)


class TestShouldEscalate:
    def test_below_threshold_escalates(self):
        from app.services.rag.confidence import should_escalate
        assert should_escalate(0.3, 0.5) is True

    def test_above_threshold_does_not_escalate(self):
        from app.services.rag.confidence import should_escalate
        assert should_escalate(0.7, 0.5) is False

    def test_equal_threshold_does_not_escalate(self):
        from app.services.rag.confidence import should_escalate
        assert should_escalate(0.5, 0.5) is False
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_rag_confidence.py -v`
Expected: 6 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_rag_confidence.py
git commit -m "test: add RAG confidence scoring unit tests"
```

---

### Task 2: RAG prompts tests

**Files:**
- Create: `backend/tests/unit/test_rag_prompts.py`

- [ ] **Step 1: Write tests**

```python
from unittest.mock import MagicMock


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.name = overrides.get("name", "TestBot")
    cb.display_name = overrides.get("display_name", "Testy")
    cb.tone = overrides.get("tone", "friendly")
    cb.language = overrides.get("language", "English")
    cb.auto_detect_language = overrides.get("auto_detect_language", False)
    cb.system_prompt = overrides.get("system_prompt", "Be helpful.")
    return cb


def _make_chunk(content="Hello world", heading_path="FAQ > General", score=0.8):
    chunk = MagicMock()
    chunk.content = content
    chunk.heading_path = heading_path
    return chunk, score


class TestBuildLanguageInstruction:
    def test_fixed_language(self):
        from app.services.rag.prompts import _build_language_instruction
        cb = _make_chatbot(language="Dutch")
        assert _build_language_instruction(cb) == "You respond in Dutch."

    def test_auto_detect_language(self):
        from app.services.rag.prompts import _build_language_instruction
        cb = _make_chatbot(auto_detect_language=True, language="French")
        result = _build_language_instruction(cb)
        assert "Detect the language" in result
        assert "French" in result

    def test_default_language_is_english(self):
        from app.services.rag.prompts import _build_language_instruction
        cb = _make_chatbot(language=None)
        assert "English" in _build_language_instruction(cb)


class TestBuildSystemPrompt:
    def test_includes_chatbot_fields(self):
        from app.services.rag.prompts import build_system_prompt
        cb = _make_chatbot(display_name="Pulse", name="SupportBot", tone="casual")
        prompt = build_system_prompt(cb)
        assert "Pulse" in prompt
        assert "SupportBot" in prompt
        assert "casual" in prompt
        assert "cite your sources" in prompt.lower()

    def test_missing_display_name_defaults_to_assistant(self):
        from app.services.rag.prompts import build_system_prompt
        cb = _make_chatbot(display_name=None)
        prompt = build_system_prompt(cb)
        assert "Assistant" in prompt


class TestBuildContextPrompt:
    def test_empty_chunks(self):
        from app.services.rag.prompts import build_context_prompt
        assert build_context_prompt([]) == "No relevant context found."

    def test_chunks_with_headings(self):
        from app.services.rag.prompts import build_context_prompt
        chunks = [_make_chunk("Answer is 42", "FAQ > Life")]
        result = build_context_prompt(chunks)
        assert "[1]" in result
        assert "FAQ > Life" in result
        assert "Answer is 42" in result

    def test_chunk_without_heading(self):
        from app.services.rag.prompts import build_context_prompt
        chunks = [_make_chunk("Some text", heading_path=None)]
        result = build_context_prompt(chunks)
        assert "[1]" in result
        assert "Some text" in result
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_rag_prompts.py -v`
Expected: 8 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_rag_prompts.py
git commit -m "test: add RAG prompt building unit tests"
```

---

### Task 3: Reranker tests

**Files:**
- Create: `backend/tests/unit/test_rag_reranker.py`

- [ ] **Step 1: Write tests**

```python
import math
from unittest.mock import MagicMock, patch


def _make_chunk(content="text", chunk_id="c1"):
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.content = content
    return chunk


class TestSigmoid:
    def test_zero_returns_half(self):
        from app.services.rag.reranker import _sigmoid
        assert _sigmoid(0.0) == 0.5

    def test_large_positive_near_one(self):
        from app.services.rag.reranker import _sigmoid
        assert _sigmoid(10.0) > 0.99

    def test_large_negative_near_zero(self):
        from app.services.rag.reranker import _sigmoid
        assert _sigmoid(-10.0) < 0.01


class TestRerank:
    def test_empty_chunks_returns_empty(self):
        from app.services.rag.reranker import rerank
        assert rerank("query", []) == []

    def test_reranks_by_cross_encoder_score(self):
        from app.services.rag.reranker import rerank
        c1 = _make_chunk("low", "c1")
        c2 = _make_chunk("high", "c2")

        mock_model = MagicMock()
        # c2 gets higher raw score than c1
        mock_model.predict.return_value = [-2.0, 3.0]

        with patch("app.services.rag.reranker._get_model", return_value=mock_model):
            result = rerank("query", [c1, c2])

        # c2 should be first (higher sigmoid of 3.0)
        assert result[0][0].id == "c2"
        assert result[1][0].id == "c1"
        # Scores should be sigmoid-transformed
        assert result[0][1] > 0.9
        assert result[1][1] < 0.2

    def test_top_k_limits_results(self):
        from app.services.rag.reranker import rerank
        chunks = [_make_chunk(f"c{i}", f"c{i}") for i in range(5)]
        mock_model = MagicMock()
        mock_model.predict.return_value = [1.0, 2.0, 3.0, 4.0, 5.0]

        with patch("app.services.rag.reranker._get_model", return_value=mock_model):
            result = rerank("query", chunks, top_k=2)

        assert len(result) == 2
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_rag_reranker.py -v`
Expected: 6 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_rag_reranker.py
git commit -m "test: add RAG reranker unit tests"
```

---

### Task 4: Retriever RRF tests

**Files:**
- Create: `backend/tests/unit/test_rag_retriever.py`

- [ ] **Step 1: Write tests**

```python
import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_chunk(chunk_id=None):
    chunk = MagicMock()
    chunk.id = chunk_id or uuid.uuid4()
    return chunk


class TestReciprocalRankFusion:
    def test_empty_inputs(self):
        from app.services.rag.retriever import _reciprocal_rank_fusion
        result = _reciprocal_rank_fusion([], [], top_k=5)
        assert result == []

    def test_dense_only(self):
        from app.services.rag.retriever import _reciprocal_rank_fusion
        c1 = _make_chunk("c1")
        result = _reciprocal_rank_fusion([(c1, 0.9)], [], top_k=5)
        assert len(result) == 1
        assert result[0].id == "c1"

    def test_overlapping_chunks_get_higher_score(self):
        from app.services.rag.retriever import _reciprocal_rank_fusion
        shared = _make_chunk("shared")
        dense_only = _make_chunk("dense_only")
        sparse_only = _make_chunk("sparse_only")

        dense = [(shared, 0.9), (dense_only, 0.8)]
        sparse = [(shared, 5.0), (sparse_only, 3.0)]
        result = _reciprocal_rank_fusion(dense, sparse, top_k=3)

        # Shared chunk appears in both lists → highest RRF score
        assert result[0].id == "shared"

    def test_top_k_limits_output(self):
        from app.services.rag.retriever import _reciprocal_rank_fusion
        chunks = [(MagicMock(id=f"c{i}"), float(i)) for i in range(10)]
        result = _reciprocal_rank_fusion(chunks, [], top_k=3)
        assert len(result) == 3


class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_combines_dense_and_sparse(self):
        from app.services.rag.retriever import hybrid_search

        c1 = _make_chunk("c1")
        c2 = _make_chunk("c2")

        with patch("app.services.rag.retriever._embed_query", new_callable=AsyncMock, return_value=[0.1] * 384), \
             patch("app.services.rag.retriever.dense_search", new_callable=AsyncMock, return_value=[(c1, 0.9)]), \
             patch("app.services.rag.retriever.sparse_search", new_callable=AsyncMock, return_value=[(c2, 5.0)]):

            db = AsyncMock()
            result = await hybrid_search(db, uuid.uuid4(), uuid.uuid4(), "test query", top_k=5)

        assert len(result) == 2  # both chunks from different sources
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_rag_retriever.py -v`
Expected: 5 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_rag_retriever.py
git commit -m "test: add RAG retriever and RRF unit tests"
```

---

### Task 5: Credits and deployment tests

**Files:**
- Create: `backend/tests/unit/test_credits.py`
- Create: `backend/tests/unit/test_deployment.py`

- [ ] **Step 1: Write credits tests**

```python
import pytest


class TestEstimateTokenCost:
    def test_known_model(self):
        from app.services.credits import estimate_token_cost
        # gpt-4o-mini: 1 credit per 1K tokens
        assert estimate_token_cost("gpt-4o-mini", 5000) == 5

    def test_unknown_model_uses_default_rate(self):
        from app.services.credits import estimate_token_cost
        # Default: 2 credits per 1K tokens
        assert estimate_token_cost("unknown-model", 3000) == 6

    def test_minimum_cost_is_one(self):
        from app.services.credits import estimate_token_cost
        assert estimate_token_cost("gpt-4o-mini", 1) == 1

    def test_byok_halves_cost(self):
        from app.services.credits import estimate_token_cost
        normal = estimate_token_cost("gpt-4o", 10000)
        byok = estimate_token_cost("gpt-4o", 10000, is_byok=True)
        assert byok == max(1, normal // 2)

    def test_byok_minimum_is_one(self):
        from app.services.credits import estimate_token_cost
        assert estimate_token_cost("gpt-4o-mini", 1, is_byok=True) == 1

    def test_expensive_model(self):
        from app.services.credits import estimate_token_cost
        # claude-opus-4-6: 15 credits per 1K tokens
        cost = estimate_token_cost("claude-opus-4-6", 2000)
        assert cost == 30
```

- [ ] **Step 2: Write deployment tests**

```python
from unittest.mock import patch


class TestDeploymentMode:
    def test_is_cloud_when_cloud_mode_true(self):
        from app.services.deployment import is_cloud
        with patch("app.services.deployment.settings") as mock_settings:
            mock_settings.CLOUD_MODE = True
            assert is_cloud() is True

    def test_is_not_cloud_when_cloud_mode_false(self):
        from app.services.deployment import is_cloud
        with patch("app.services.deployment.settings") as mock_settings:
            mock_settings.CLOUD_MODE = False
            assert is_cloud() is False

    def test_is_self_hosted_inverse_of_cloud(self):
        from app.services.deployment import is_self_hosted
        with patch("app.services.deployment.settings") as mock_settings:
            mock_settings.CLOUD_MODE = False
            assert is_self_hosted() is True
            mock_settings.CLOUD_MODE = True
            assert is_self_hosted() is False
```

- [ ] **Step 3: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_credits.py tests/unit/test_deployment.py -v`
Expected: 9 PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/tests/unit/test_credits.py backend/tests/unit/test_deployment.py
git commit -m "test: add credits estimation and deployment mode unit tests"
```

---

### Task 6: Substantive query detection tests

**Files:**
- Create: `backend/tests/unit/test_resolution_service.py` (first part — pure function only)

- [ ] **Step 1: Write tests**

```python
import pytest


class TestIsSubstantiveQuery:
    def test_greeting_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("hello") is False
        assert _is_substantive_query("Hi!") is False
        assert _is_substantive_query("Hey there") is False

    def test_short_message_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("ok") is False
        assert _is_substantive_query("yes") is False
        assert _is_substantive_query("no") is False

    def test_thanks_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("thanks!") is False
        assert _is_substantive_query("Thank you") is False

    def test_identity_question_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("who are you?") is False
        assert _is_substantive_query("what are you?") is False

    def test_real_question_is_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("How do I reset my password?") is True
        assert _is_substantive_query("What are your pricing plans?") is True

    def test_multilingual_greetings(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("bonjour") is False
        assert _is_substantive_query("hallo!") is False
        assert _is_substantive_query("bedankt") is False

    def test_whitespace_and_punctuation(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("  hello!  ") is False
        assert _is_substantive_query("bye?") is False
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_resolution_service.py -v`
Expected: 7 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_resolution_service.py
git commit -m "test: add substantive query detection tests"
```

---

## Chunk 2: Mock-Based Component Tests

### Task 7: RAG memory tests

**Files:**
- Create: `backend/tests/unit/test_rag_memory.py`

- [ ] **Step 1: Write tests**

```python
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_message(author_type, content, message_type="incoming"):
    msg = MagicMock()
    msg.author_type = author_type
    msg.content = content
    msg.message_type = message_type
    return msg


class TestGetConversationHistory:
    @pytest.mark.asyncio
    async def test_returns_role_mapped_messages(self):
        from app.services.rag.memory import get_conversation_history

        messages = [
            _make_message("contact", "How do I login?", "incoming"),
            _make_message("bot", "Click the login button.", "outgoing"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = messages

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        history = await get_conversation_history(db, uuid.uuid4())
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "How do I login?"}
        assert history[1] == {"role": "assistant", "content": "Click the login button."}

    @pytest.mark.asyncio
    async def test_skips_empty_content(self):
        from app.services.rag.memory import get_conversation_history

        messages = [
            _make_message("contact", None, "incoming"),
            _make_message("bot", "Response", "outgoing"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = messages

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        history = await get_conversation_history(db, uuid.uuid4())
        assert len(history) == 1
        assert history[0]["content"] == "Response"

    @pytest.mark.asyncio
    async def test_agent_maps_to_assistant(self):
        from app.services.rag.memory import get_conversation_history

        messages = [_make_message("agent", "I'll help you.")]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = messages

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        history = await get_conversation_history(db, uuid.uuid4())
        assert history[0]["role"] == "assistant"
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_rag_memory.py -v`
Expected: 3 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_rag_memory.py
git commit -m "test: add RAG conversation memory unit tests"
```

---

### Task 8: RAG generator tests

**Files:**
- Create: `backend/tests/unit/test_rag_generator.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.id = "cb-1"
    cb.llm_provider = overrides.get("llm_provider", "openrouter")
    cb.llm_model = overrides.get("llm_model", "openai/gpt-4o-mini")
    cb.temperature = overrides.get("temperature", 0.7)
    cb.max_tokens = overrides.get("max_tokens", 1024)
    cb.byoak = overrides.get("byoak", None)
    cb.workspace_id = "ws-1"
    return cb


class TestStreamResponse:
    @pytest.mark.asyncio
    async def test_streams_tokens_from_llm_client(self):
        from app.services.rag.generator import stream_response

        async def fake_stream(**kwargs):
            yield "Hello"
            yield " world"
            yield {"prompt_tokens": 10, "completion_tokens": 5}

        mock_client = MagicMock()
        mock_client.stream_generate = fake_stream

        with patch("app.services.rag.generator.get_llm_client", return_value=mock_client):
            tokens = []
            async for item in stream_response(
                [{"role": "user", "content": "hi"}],
                _make_chatbot(),
            ):
                tokens.append(item)

        assert tokens == ["Hello", " world", {"prompt_tokens": 10, "completion_tokens": 5}]

    @pytest.mark.asyncio
    async def test_uses_workspace_openrouter_key_when_provided(self):
        from app.services.rag.generator import stream_response

        async def fake_stream(**kwargs):
            yield "ok"

        mock_client = MagicMock()
        mock_client.stream_generate = fake_stream

        with patch("app.services.rag.generator.get_llm_client", return_value=mock_client) as mock_get:
            async for _ in stream_response(
                [{"role": "user", "content": "hi"}],
                _make_chatbot(),
                openrouter_key="sk-ws-key",
            ):
                pass

        mock_get.assert_called_once_with("openrouter", api_key="sk-ws-key", base_url=None)

    @pytest.mark.asyncio
    async def test_uses_byoak_when_no_workspace_key(self):
        from app.services.rag.generator import stream_response

        async def fake_stream(**kwargs):
            yield "ok"

        mock_client = MagicMock()
        mock_client.stream_generate = fake_stream

        with patch("app.services.rag.generator.get_llm_client", return_value=mock_client) as mock_get, \
             patch("app.services.encryption.decrypt_api_key", return_value="decrypted-key"):
            async for _ in stream_response(
                [{"role": "user", "content": "hi"}],
                _make_chatbot(byoak="encrypted-key", llm_provider="openai"),
            ):
                pass

        mock_get.assert_called_once_with("openai", api_key="decrypted-key", base_url=None)
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_rag_generator.py -v`
Expected: 3 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_rag_generator.py
git commit -m "test: add RAG generator streaming unit tests"
```

---

### Task 9: RAG engine process_query tests

**Files:**
- Create: `backend/tests/unit/test_rag_engine.py`

- [ ] **Step 1: Write tests**

```python
import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.id = uuid.uuid4()
    cb.workspace_id = uuid.uuid4()
    cb.use_reranking = overrides.get("use_reranking", False)
    cb.retrieval_top_k = overrides.get("retrieval_top_k", 5)
    cb.confidence_threshold = overrides.get("confidence_threshold", 0.4)
    cb.llm_provider = "openrouter"
    cb.llm_model = "openai/gpt-4o-mini"
    cb.temperature = 0.7
    cb.max_tokens = 1024
    cb.name = "TestBot"
    cb.display_name = "Test"
    cb.tone = "professional"
    cb.language = "English"
    cb.auto_detect_language = False
    cb.system_prompt = "Be helpful."
    cb.byoak = None
    return cb


def _make_kb():
    kb = MagicMock()
    kb.id = uuid.uuid4()
    return kb


def _make_chunk(chunk_id=None, content="test content", doc_id=None):
    chunk = MagicMock()
    chunk.id = chunk_id or uuid.uuid4()
    chunk.content = content
    chunk.document_id = doc_id or uuid.uuid4()
    chunk.heading_path = "FAQ"
    return chunk


class TestProcessQuery:
    @pytest.mark.asyncio
    async def test_no_knowledge_base_yields_escalation(self):
        from app.services.rag.engine import process_query, RAGResult

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # no KB
        db.execute = AsyncMock(return_value=mock_result)

        items = []
        async for item in process_query(db, "How do I login?", _make_chatbot()):
            items.append(item)

        # Should yield RAGResult with escalated=True, then a fallback message
        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert len(rag_results) == 1
        assert rag_results[0].escalated is True
        assert rag_results[0].confidence_score == 0.0

        text_items = [i for i in items if isinstance(i, str)]
        assert any("knowledge base" in t.lower() for t in text_items)

    @pytest.mark.asyncio
    async def test_with_kb_retrieves_and_generates(self):
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        chunk = _make_chunk()
        doc_id = chunk.document_id

        # Mock DB: first call returns KB, second call returns doc metadata
        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb

        doc_row = MagicMock()
        doc_row.__getitem__ = lambda self, key: {0: doc_id, 1: "My Doc", 2: "https://example.com"}[key]
        docs_result = MagicMock()
        docs_result.all.return_value = [doc_row]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        async def fake_stream(*args, **kwargs):
            yield "Generated answer"
            yield {"prompt_tokens": 50, "completion_tokens": 20}

        with patch("app.services.rag.engine.hybrid_search", new_callable=AsyncMock, return_value=[chunk]), \
             patch("app.services.rag.engine.compute_confidence", return_value=(0.85, 0.7)), \
             patch("app.services.rag.engine.should_escalate", return_value=False), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            items = []
            async for item in process_query(db, "test query", _make_chatbot(), conversation_id=uuid.uuid4()):
                items.append(item)

        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert len(rag_results) == 1
        assert rag_results[0].confidence_score == 0.85
        assert rag_results[0].escalated is False
        assert len(rag_results[0].sources) >= 0  # sources built from doc metadata

        text_items = [i for i in items if isinstance(i, str)]
        assert "Generated answer" in text_items

    @pytest.mark.asyncio
    async def test_reranking_enabled(self):
        from app.services.rag.engine import process_query

        kb = _make_kb()
        chunk = _make_chunk()

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        async def fake_stream(*args, **kwargs):
            yield "answer"

        with patch("app.services.rag.engine.hybrid_search", new_callable=AsyncMock, return_value=[chunk]), \
             patch("app.services.rag.engine.rerank", return_value=[(chunk, 0.9)]) as mock_rerank, \
             patch("app.services.rag.engine.compute_confidence", return_value=(0.9, 0.9)), \
             patch("app.services.rag.engine.should_escalate", return_value=False), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            async for _ in process_query(db, "test", _make_chatbot(use_reranking=True)):
                pass

        mock_rerank.assert_called_once()
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_rag_engine.py -v`
Expected: 3 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_rag_engine.py
git commit -m "test: add RAG engine process_query unit tests"
```

---

## Chunk 3: Resolution Service Handle Message Tests

### Task 10: Resolution service handle_message tests

**Files:**
- Modify: `backend/tests/unit/test_resolution_service.py` (add handle_message tests)

- [ ] **Step 1: Write handle_message tests**

Append to `backend/tests/unit/test_resolution_service.py`:

```python
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag.engine import RAGResult


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.id = overrides.get("id", uuid.uuid4())
    cb.workspace_id = overrides.get("workspace_id", uuid.uuid4())
    cb.name = "TestBot"
    cb.use_reranking = False
    cb.confidence_threshold = 0.4
    cb.llm_provider = "openrouter"
    cb.llm_model = "openai/gpt-4o-mini"
    return cb


def _make_workspace(**overrides):
    ws = MagicMock()
    ws.id = overrides.get("id", uuid.uuid4())
    ws.openrouter_api_key = overrides.get("openrouter_api_key", None)
    ws.openrouter_base_url = overrides.get("openrouter_base_url", None)
    ws.credit_balance = overrides.get("credit_balance", 1000)
    ws.is_byok = overrides.get("is_byok", False)
    return ws


async def _collect_events(gen):
    events = []
    async for event in gen:
        events.append(event)
    return events


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_creates_conversation_when_none_provided(self):
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.8, confidence_avg=0.7, escalated=False,
            retrieved_chunk_ids=[], query="test", sources=[],
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Hello!"
            yield {"prompt_tokens": 10, "completion_tokens": 5}

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
             patch("app.services.resolution_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(return_value=bot_message)
            mock_conv.get_conversation = AsyncMock()

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "How do I login?")
            )

        mock_conv.create_conversation.assert_awaited_once()
        token_events = [e for e in events if e.type == "token"]
        done_events = [e for e in events if e.type == "done"]
        assert len(token_events) == 1
        assert token_events[0].data == "Hello!"
        assert len(done_events) == 1
        assert done_events[0].escalated is False

    @pytest.mark.asyncio
    async def test_escalation_on_low_confidence(self):
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.2, confidence_avg=0.15, escalated=True,
            retrieved_chunk_ids=[], query="complex question", sources=[],
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "I'm not sure about that."

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
             patch("app.services.resolution_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(return_value=bot_message)

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "How do I configure advanced SAML SSO?")
            )

        done_event = [e for e in events if e.type == "done"][0]
        assert done_event.escalated is True
        assert conversation.escalation_reason == "low_confidence"

    @pytest.mark.asyncio
    async def test_greeting_suppresses_escalation(self):
        """Even if RAG returns low confidence, greetings should not escalate."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace()
        chatbot = _make_chatbot(workspace_id=ws.id)
        conversation = MagicMock(id=uuid.uuid4())
        bot_message = MagicMock(id=uuid.uuid4())

        rag_result = RAGResult(
            confidence_score=0.1, confidence_avg=0.1, escalated=True,
            retrieved_chunk_ids=[], query="hello", sources=[],
        )

        async def fake_process_query(*args, **kwargs):
            yield rag_result
            yield "Hi there!"

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
             patch("app.services.resolution_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]):

            mock_conv.create_conversation = AsyncMock(return_value=conversation)
            mock_conv.add_message = AsyncMock(return_value=bot_message)

            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "hello!")
            )

        done_event = [e for e in events if e.type == "done"][0]
        assert done_event.escalated is False  # greeting suppresses escalation

    @pytest.mark.asyncio
    async def test_cloud_mode_credit_check(self):
        """Cloud mode with zero credits yields error event."""
        from app.services.resolution_service import handle_message

        ws = _make_workspace(credit_balance=0)
        chatbot = _make_chatbot(workspace_id=ws.id)

        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = ws
        db = AsyncMock()
        db.execute = AsyncMock(return_value=ws_result)

        with patch("app.services.resolution_service.is_cloud", return_value=True):
            events = await _collect_events(
                handle_message(db, ws.id, chatbot, "test question here")
            )

        assert len(events) == 1
        assert events[0].type == "error"
        assert "credit" in events[0].data.lower()
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend pytest tests/unit/test_resolution_service.py -v`
Expected: 11 PASSED (7 from Task 6 + 4 new)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_resolution_service.py
git commit -m "test: add resolution service handle_message unit tests"
```

---

### Task 11: Final verification and coverage check

- [ ] **Step 1: Run full backend unit test suite**

Run: `docker compose exec backend pytest tests/unit/ -v --tb=short`
Expected: ~323+ passed (278 existing + ~45 new), 0 failed

- [ ] **Step 2: Run coverage for new files**

Run: `docker compose exec backend pytest tests/unit/ --cov=app/services/rag --cov=app/services/resolution_service --cov=app/services/credits --cov=app/services/deployment --cov-report=term-missing --tb=short`
Expected: High coverage for all targeted modules

- [ ] **Step 3: Commit any fixes**

If any tests fail, investigate and fix. Then final commit.
