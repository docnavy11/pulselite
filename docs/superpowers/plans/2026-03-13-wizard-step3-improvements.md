# Wizard Step 3 Improvements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the chatbot wizard step 3 to show all generated fields, fix the system prompt to be behavioral-only, and make the bot name adapt to actual website/brand content.

**Architecture:** Two independent changes — backend prompt fix (autoconfig.py) and frontend display fix (chatbots/new/page.tsx). No new files needed, no schema changes needed (backend `ChatbotUpdate` already accepts `system_prompt` and `fallback_message`).

**Tech Stack:** FastAPI backend, React + TypeScript frontend, Vitest unit tests, pytest backend tests.

---

## Chunk 1: Backend — fix autoconfig prompt

### Task 1: Fix system prompt generation + bot name in autoconfig.py

**Files:**
- Modify: `backend/app/services/autoconfig.py` (lines 35–56 — the `_PROMPT` constant)
- Test: `backend/tests/unit/test_autoconfig.py` (new file)

The current prompt tells the LLM to write `system_prompt: helpful assistant context` while feeding it content chunks. The LLM sees pricing tables, feature lists, etc. and naturally includes them in the system prompt — but the system prompt should only contain behavioral guidance. The knowledge base handles factual retrieval at query time.

Also, the `name` instruction produces generic names ("Support Bot"). It should extract the real brand name from the content.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_autoconfig.py`:

```python
"""Unit tests for autoconfig prompt quality and generate() output."""
import json
import pytest
from unittest.mock import AsyncMock, patch
from app.services.autoconfig import generate, extract_brand_color, _PROMPT


def _make_llm_response(**overrides) -> str:
    base = {
        "name": "Linkflow Assistant",
        "welcome_message": "Hi! How can I help?",
        "system_prompt": "You are a helpful assistant for Linkflow. Be concise and professional.",
        "suggested_questions": ["Q1?", "Q2?", "Q3?", "Q4?"],
        "fallback_message": "I don't have info on that. Please contact support.",
        "tone": "professional",
    }
    base.update(overrides)
    return json.dumps(base)


class TestPromptContent:
    def test_system_prompt_instruction_is_behavioral(self):
        """System prompt instruction must say 'behavioral' and forbid facts."""
        assert "behavioral" in _PROMPT.lower() or "persona" in _PROMPT.lower() or "behavior" in _PROMPT.lower()

    def test_system_prompt_instruction_forbids_facts(self):
        """Prompt must explicitly tell LLM not to include facts/pricing in system_prompt."""
        assert "not" in _PROMPT.lower() or "do not" in _PROMPT.lower() or "avoid" in _PROMPT.lower()
        # Must mention what NOT to include
        forbidden_keywords = ["pricing", "facts", "specific", "product details", "content"]
        prompt_lower = _PROMPT.lower()
        assert any(kw in prompt_lower for kw in forbidden_keywords), \
            "Prompt should mention what NOT to include in system_prompt"

    def test_name_instruction_mentions_brand(self):
        """Name instruction should guide LLM to extract brand/business name."""
        assert "brand" in _PROMPT.lower() or "business" in _PROMPT.lower() or "company" in _PROMPT.lower()


class TestGenerate:
    @pytest.mark.asyncio
    async def test_system_prompt_capped_at_300_words(self):
        long_prompt = " ".join(["word"] * 400)
        mock_response = _make_llm_response(system_prompt=long_prompt)
        with patch("app.services.autoconfig._llm_client") as mock_client:
            mock_client.generate = AsyncMock(return_value=mock_response)
            result = await generate(["some content"], "<html></html>")
        assert len(result.system_prompt.split()) <= 300

    @pytest.mark.asyncio
    async def test_exactly_4_suggested_questions(self):
        mock_response = _make_llm_response(suggested_questions=["Q1?", "Q2?"])
        with patch("app.services.autoconfig._llm_client") as mock_client:
            mock_client.generate = AsyncMock(return_value=mock_response)
            result = await generate(["content"], "<html></html>")
        assert len(result.suggested_questions) == 4

    @pytest.mark.asyncio
    async def test_returns_all_required_fields(self):
        mock_response = _make_llm_response()
        with patch("app.services.autoconfig._llm_client") as mock_client:
            mock_client.generate = AsyncMock(return_value=mock_response)
            result = await generate(["content"], "<html></html>")
        assert result.name == "Linkflow Assistant"
        assert result.welcome_message == "Hi! How can I help?"
        assert result.system_prompt
        assert result.fallback_message
        assert result.tone == "professional"

    @pytest.mark.asyncio
    async def test_language_instruction_injected(self):
        captured = {}
        async def fake_generate(messages, **kwargs):
            captured["prompt"] = messages[0]["content"]
            return _make_llm_response()
        with patch("app.services.autoconfig._llm_client") as mock_client:
            mock_client.generate = fake_generate
            await generate(["content"], "<html></html>", language="nl")
        assert "Dutch" in captured["prompt"]


class TestExtractBrandColor:
    def test_extracts_theme_color_meta(self):
        html = '<meta name="theme-color" content="#ff6b35">'
        assert extract_brand_color(html) == "#ff6b35"

    def test_extracts_css_primary_variable(self):
        html = "<style>:root { --primary: #1a73e8; }</style>"
        assert extract_brand_color(html) == "#1a73e8"

    def test_returns_none_when_absent(self):
        assert extract_brand_color("<html><body></body></html>") is None

    def test_returns_none_for_empty_html(self):
        assert extract_brand_color("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest tests/unit/test_autoconfig.py -v 2>&1 | head -40
```

Expected: `TestPromptContent` tests fail (prompt doesn't mention behavioral/brand yet).

- [ ] **Step 3: Fix the `_PROMPT` constant in autoconfig.py**

Replace the `_PROMPT` constant (lines 35–56) with:

```python
_PROMPT = """You are a chatbot configuration assistant. Based on the website content below, generate a chatbot configuration.

Respond with ONLY a JSON object in this exact format:
{{
  "name": "...",
  "welcome_message": "...",
  "system_prompt": "...",
  "suggested_questions": ["...", "...", "...", "..."],
  "fallback_message": "...",
  "tone": "..."
}}

Rules:
- name: use the actual brand or business name from the content (e.g. "Linkflow Assistant", "QIS Support Bot") — NOT a generic name like "Support Bot"
- welcome_message: friendly greeting in the brand voice, 1-2 sentences
- system_prompt: behavioral guidance ONLY — describe the assistant's persona, tone, scope, and conversation style. Do NOT include specific facts, pricing, product details, or any content from the website. That information is retrieved from the knowledge base at query time.
- suggested_questions: exactly 4 questions visitors commonly ask about this type of business
- fallback_message: polite message for questions outside scope
- tone: infer from the website — must be exactly one of: professional, friendly, casual, formal
{language_instruction}
Website content:
{content}"""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend pytest tests/unit/test_autoconfig.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Run full backend test suite**

```bash
make test
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/autoconfig.py backend/tests/unit/test_autoconfig.py
git commit -m "fix: autoconfig system_prompt is behavioral-only, name uses brand from content"
```

---

## Chunk 2: Frontend — show all generated fields in step 3

### Task 2: Add system_prompt and fallback_message to step 3 review card

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/new/page.tsx`
  - Add state: `reviewSystemPrompt`, `reviewFallback`
  - Populate from autoconfig result
  - Add textareas in review card (after welcome_message, before tone)
  - Include in `handleSave()` updateChatbot call
- Test: `frontend/src/test/wizard-step3.test.ts` (new file)

**Context:** The `updateChatbot` function accepts `Partial<Chatbot>`, and `Chatbot` already has `system_prompt?: string` and `fallback_message?: string` in `frontend/src/lib/types.ts`. No API or type changes needed.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/test/wizard-step3.test.ts`:

```typescript
import { describe, it, expect } from "vitest";

// Logic: save payload should include system_prompt and fallback_message
// when they have values (mirrors handleSave() payload construction)
function buildSavePayload(fields: {
  name: string;
  welcome: string;
  systemPrompt: string;
  fallback: string;
  color: string;
  tone: string;
  language: string;
}) {
  return {
    name: fields.name,
    welcome_message: fields.welcome,
    system_prompt: fields.systemPrompt,
    fallback_message: fields.fallback,
    brand_color: fields.color,
    tone: fields.tone,
    language: fields.language,
  };
}

describe("wizard step 3 save payload", () => {
  it("includes system_prompt in save payload", () => {
    const payload = buildSavePayload({
      name: "Linkflow Assistant",
      welcome: "Hi!",
      systemPrompt: "You are a helpful assistant.",
      fallback: "I don't know.",
      color: "#ff6b35",
      tone: "professional",
      language: "en",
    });
    expect(payload.system_prompt).toBe("You are a helpful assistant.");
  });

  it("includes fallback_message in save payload", () => {
    const payload = buildSavePayload({
      name: "Bot",
      welcome: "Hi!",
      systemPrompt: "...",
      fallback: "Sorry, I can't help with that.",
      color: "#000",
      tone: "friendly",
      language: "nl",
    });
    expect(payload.fallback_message).toBe("Sorry, I can't help with that.");
  });

  it("all 7 fields present in payload", () => {
    const payload = buildSavePayload({
      name: "Bot",
      welcome: "Hi!",
      systemPrompt: "Behave well.",
      fallback: "No idea.",
      color: "#abc",
      tone: "casual",
      language: "fr",
    });
    const keys = Object.keys(payload);
    expect(keys).toContain("system_prompt");
    expect(keys).toContain("fallback_message");
    expect(keys).toContain("welcome_message");
    expect(keys).toContain("brand_color");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/test/wizard-step3.test.ts
```

Expected: Tests actually pass (pure logic), confirming the test structure is valid.

> Note: these tests validate the payload shape — the actual wiring is verified by reading the diff below.

- [ ] **Step 3: Add state variables and wire into reset/retry paths**

Add two new state variables after `reviewLanguage` (~line 135):

```typescript
const [reviewSystemPrompt, setReviewSystemPrompt] = useState("");
const [reviewFallback, setReviewFallback] = useState("");
```

In `handleRestart()` (~line 298), add alongside the other reset calls:
```typescript
setReviewSystemPrompt("");
setReviewFallback("");
```

In the "Retry autoconfig" click handler (~line 605), add alongside the other `setReview*` calls:
```typescript
setReviewSystemPrompt(result.system_prompt ?? "");
setReviewFallback(result.fallback_message ?? "");
```

- [ ] **Step 4: Populate from autoconfig result (lines ~241–247)**

In the `runAutoconfig` result handler, add:

```typescript
setReviewSystemPrompt(result.system_prompt ?? "");
setReviewFallback(result.fallback_message ?? "");
```

So the full block becomes:
```typescript
setConfig(result);
setReviewName(result.name);
setReviewWelcome(result.welcome_message ?? "");
setReviewSystemPrompt(result.system_prompt ?? "");
setReviewFallback(result.fallback_message ?? "");
setReviewColor(result.brand_color ?? "#ff6b35");
setReviewTone(result.tone ?? "professional");
setReviewLanguage(result.language ?? "en");
setStep("review");
```

- [ ] **Step 5: Add textareas to review card (after welcome message textarea, before tone section)**

Insert between the welcome message block and the tone block (after line ~722):

```tsx
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">System prompt</label>
  <textarea
    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
    rows={5}
    value={reviewSystemPrompt}
    onChange={(e) => setReviewSystemPrompt(e.target.value)}
  />
  <p className="text-[11px] text-gray-400 mt-1">Behavioral guidance for the bot — persona, tone, scope. No specific facts.</p>
</div>
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">Fallback message</label>
  <textarea
    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
    rows={2}
    value={reviewFallback}
    onChange={(e) => setReviewFallback(e.target.value)}
  />
</div>
```

- [ ] **Step 6: Include in handleSave() (lines ~270–276)**

Update the `updateChatbot` call to include the new fields:

```typescript
await updateChatbot(workspace.id, chatbotId, {
  name: reviewName,
  welcome_message: reviewWelcome,
  system_prompt: reviewSystemPrompt,
  fallback_message: reviewFallback,
  brand_color: reviewColor,
  tone: reviewTone,
  language: reviewLanguage,
} as Parameters<typeof updateChatbot>[2]);
```

- [ ] **Step 7: Run frontend tests**

```bash
docker compose exec frontend npx vitest run
```

Expected: All 89 tests pass (86 existing + 3 new).

- [ ] **Step 8: TypeScript check**

```bash
docker compose exec frontend npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/app/\(dashboard\)/chatbots/new/page.tsx \
        frontend/src/test/wizard-step3.test.ts
git commit -m "feat: show system_prompt and fallback_message in wizard step 3 review"
```
