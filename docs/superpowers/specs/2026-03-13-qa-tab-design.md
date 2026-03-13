# Q&A Tab — Design Spec

## Overview

Add a **Q&A tab** to the chatbot detail view that auto-generates realistic user questions based on knowledge base content, tests them through the full RAG chat pipeline, and displays results with quality flags. Users can edit pairs, request better answers, and feed improved Q&A back into the knowledge base.

## Goals

- Let chatbot owners audit answer quality without manually typing test questions
- Surface low-confidence and escalated responses so users know where their KB has gaps
- Create a feedback loop: generate → test → identify gaps → improve KB → re-test

## Data Model

New table `qa_pairs`:

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| workspace_id | UUID (FK) | Tenant isolation |
| chatbot_id | UUID (FK) | Parent chatbot |
| question | text | The generated or edited question |
| answer | text, nullable | Null while pending/testing |
| suggested_answer | text, nullable | LLM-generated better answer |
| status | varchar | `pending`, `testing`, `completed`, `failed` |
| confidence_score | float, nullable | From RAG pipeline |
| escalated | bool, default false | Whether confidence < threshold |
| sources | JSONB, nullable | Retrieved chunk IDs/titles |
| is_edited | bool, default false | True if human modified Q or A |
| kb_document_id | UUID (FK to documents), nullable | Set when "Add to KB" is used; null = not added |
| error_message | text, nullable | Error details if status=failed |
| created_at | timestamp | |
| updated_at | timestamp | |

No run/batch/versioning — flat list per chatbot. New generations append.

## Backend Architecture

### Celery Tasks

**`generate_qa(chatbot_id, count)`**
1. Load chatbot + KB + chunks sampled evenly across documents (up to ~50 chunks total, round-robin across docs for topic coverage)
2. Call LLM with prompt: "Given this knowledge base content, generate N realistic questions a user would ask"
3. Deduplicate against existing QA pairs via normalized exact-match (lowercase, strip punctuation). Skip duplicates.
4. Insert N `QAPair` rows with `status=pending`
5. For each pair, dispatch `test_qa_question.delay(qa_pair_id)`
6. Emit `qa:questions_generated` via Socket.IO to the chatbot's workspace room

**`test_qa_question(qa_pair_id)`**
1. Load QAPair → chatbot → workspace_id
2. Call `process_query(db, query=question, chatbot=chatbot, conversation_id=None)` from `rag/engine.py` — this already supports `conversation_id=None` and does not create conversations or contacts
3. Consume the full async generator, collecting token strings into the answer and extracting the `RAGResult` for confidence_score, escalated flag, and source chunk references
4. Update QAPair: `status=completed`, populate answer + confidence_score + escalated + sources
5. On exception: set `status=failed`, `error_message=str(exc)`
6. Emit `qa:pair_updated` via Socket.IO with full payload (including answer text to avoid extra round-trip)

**`suggest_qa_answer(qa_pair_id)`**
1. Load QAPair + relevant KB chunks for the question
2. LLM prompt includes the original (poor) answer as context: "Given this knowledge base content and question, write the best possible answer. The chatbot previously generated this response: {answer}. Write a clearer, more accurate answer."
3. Save result to `suggested_answer` field
4. Emit `qa:pair_updated` via Socket.IO

### RAG Pipeline Reuse

No refactor of `handle_message()` needed. The `process_query()` function in `rag/engine.py` already accepts `conversation_id=None` and handles the full RAG pipeline (hybrid retrieval, reranking, confidence scoring, LLM generation) without creating conversations or contacts. The test task calls it directly via `asyncio.run()` inside the Celery task.

### Concurrency Guard

Use an atomic DB check: before starting generation, query `SELECT count(*) FROM qa_pairs WHERE chatbot_id = :id AND status IN ('pending', 'testing')`. If > 0, return 409 Conflict. This is consistent with the atomic-UPDATE guard pattern used elsewhere (e.g. autoconfig triggering).

### API Endpoints

All under `/api/v1/workspaces/{workspace_id}/chatbots/{chatbot_id}/qa`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/qa` | List QA pairs. Supports `?status=completed&page=1&page_size=20` |
| POST | `/qa/generate` | Start generation. Body: `{ count: 10 }`. Returns `{ status: "queued", count }` |
| PUT | `/qa/{id}` | Edit question/answer. Sets `is_edited=true` |
| DELETE | `/qa/{id}` | Remove a pair |
| POST | `/qa/{id}/suggest` | Generate a better answer via LLM |
| POST | `/qa/{id}/retest` | Re-run single question through pipeline |
| POST | `/qa/{id}/add-to-kb` | Save Q&A as text document in chatbot's KB |

### Pydantic Schemas

```python
class GenerateQARequest(BaseModel):
    count: int = Field(ge=1, le=50, default=10)

class QAPairUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None

class QAPairResponse(BaseModel):
    id: uuid.UUID
    chatbot_id: uuid.UUID
    question: str
    answer: str | None
    suggested_answer: str | None
    status: str
    confidence_score: float | None
    escalated: bool
    sources: list[dict] | None
    is_edited: bool
    kb_document_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class QAPairListResponse(BaseModel):
    items: list[QAPairResponse]
    total: int
```

### Add to KB Flow

Creates a new Document in the chatbot's primary KB:
- `source_type="qa"`
- `title` = question text
- `raw_content` = `Q: {question}\nA: {answer}` (matches `qa_chunker` parsing expectations)
- Triggers `ingest_document.delay(doc_id)` for normal chunking + embedding
- Sets `qa_pair.kb_document_id` to the new document's ID

### Socket.IO Events

| Event | Payload | When |
|-------|---------|------|
| `qa:questions_generated` | `{ chatbot_id, count }` | After question generation completes |
| `qa:pair_updated` | `{ qa_pair_id, status, confidence_score, escalated, answer, suggested_answer }` | After each question is tested or suggested answer is ready |

Events are emitted to the workspace room via `emit_to_workspace(workspace_id, event, data)`.

## Frontend

### Tab Placement

New tab **Q&A** added to chatbot detail layout at position index 6 (between Test and Publish). Route: `/chatbots/{id}/qa`. Icon: `MessageSquareText` from lucide-react.

### Empty State

"No Q&A pairs yet. Generate questions to test how your chatbot handles real user queries." with a "Generate" button.

### Header Bar

- Summary stats: `12 pairs · 9 good · 2 low confidence · 1 escalated`
- "Generate" button → popover to pick count (10 / 25 / 50), confirm
- Disabled with "Generation in progress..." when any pairs have status `pending` or `testing`

### Q&A List

Card-based layout with pagination (20 per page), each card:
- **Question** — markdown rendered, click to edit inline
- **Answer** — markdown rendered, click to edit inline
- **Confidence badge** — green (≥ 0.75), yellow (≥ 0.50), red (< 0.50)
- **"Escalated" tag** if bot would have handed off
- **Source chunks** — collapsible list of referenced chunks
- **Status indicator** — spinner while `pending` or `testing`; error message if `failed`

Action buttons per card:
- **Suggest answer** — visible on low-confidence/escalated pairs. Shows result in a distinct panel with "Use this answer" button
- **Add to KB** — saves Q&A as document. Shows "Added to KB" (disabled) when `kb_document_id` is set
- **Re-test** — re-runs through pipeline
- **Delete** — removes the pair

### Filtering & Sorting

- Filter: All / Low confidence / Escalated / Failed
- Sort: newest first (default)

### Real-time Updates

- `qa:questions_generated` → refresh list, show pending cards
- `qa:pair_updated` → update individual card in-place with answer + confidence from event payload

## Constraints

- **KB size guard**: If KB has < 5 chunks, warn user and suggest fewer questions
- **Concurrency**: One generation job per chatbot at a time (enforced via DB status check, returns 409)
- **Limits**: Max 50 questions per generation, max 200 QA pairs per chatbot
- **Deduplication**: Normalized exact-match (lowercase, strip punctuation) against existing pairs. Skip duplicates.
- **No conversations**: Testing does not create Conversation or Contact records
- **Chunk sampling**: Chunks are sampled evenly across documents (round-robin) for topic coverage, not just the first N by insertion order
- **Credit consumption**: Q&A testing and suggestion LLM calls consume from the workspace credit balance like any other LLM call
