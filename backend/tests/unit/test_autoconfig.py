# backend/tests/unit/test_autoconfig.py
"""Unit tests for autoconfig prompt quality and generate() output."""
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.services.autoconfig import AutoConfigResult, extract_brand_color, generate, _PROMPT


def _make_llm_response(**overrides) -> str:
    """Helper to create a mock LLM response with optional overrides."""
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
    """Verify that _PROMPT guides LLM toward behavioral-only system prompts."""

    def test_system_prompt_instruction_is_behavioral(self):
        """System prompt instruction must say 'behavioral' and forbid facts."""
        prompt_lower = _PROMPT.lower()
        assert "behavioral" in prompt_lower or "persona" in prompt_lower or "behavior" in prompt_lower, \
            "_PROMPT must mention 'behavioral', 'behavior', or 'persona'"

    def test_system_prompt_instruction_forbids_facts(self):
        """Prompt must explicitly tell LLM not to include facts/pricing in system_prompt."""
        prompt_lower = _PROMPT.lower()
        # Must contain some negation
        assert "not" in prompt_lower or "do not" in prompt_lower or "avoid" in prompt_lower, \
            "_PROMPT must contain negation (not/do not/avoid)"
        # Must mention what NOT to include
        forbidden_keywords = ["pricing", "facts", "specific", "product details", "content"]
        assert any(kw in prompt_lower for kw in forbidden_keywords), \
            "Prompt should mention what NOT to include in system_prompt (pricing, facts, etc.)"

    def test_name_instruction_mentions_brand(self):
        """Name instruction should guide LLM to extract brand/business name."""
        prompt_lower = _PROMPT.lower()
        assert "brand" in prompt_lower or "business" in prompt_lower or "company" in prompt_lower, \
            "_PROMPT must mention extracting 'brand', 'business', or 'company' name"


class TestGenerate:
    """Test generate() output constraints."""

    @pytest.mark.asyncio
    async def test_system_prompt_capped_at_300_words(self):
        """Verify system_prompt is capped at 300 words."""
        long_prompt = " ".join(["word"] * 400)
        mock_response = _make_llm_response(system_prompt=long_prompt)
        with patch("app.services.autoconfig._llm_client") as mock_client:
            mock_client.generate = AsyncMock(return_value=mock_response)
            result = await generate(["some content"], "<html></html>")
        assert len(result.system_prompt.split()) <= 300, \
            f"system_prompt has {len(result.system_prompt.split())} words, should be <= 300"

    @pytest.mark.asyncio
    async def test_exactly_4_suggested_questions(self):
        """Verify suggested_questions is always exactly 4 items."""
        mock_response = _make_llm_response(suggested_questions=["Q1?", "Q2?"])
        with patch("app.services.autoconfig._llm_client") as mock_client:
            mock_client.generate = AsyncMock(return_value=mock_response)
            result = await generate(["content"], "<html></html>")
        assert len(result.suggested_questions) == 4, \
            f"suggested_questions has {len(result.suggested_questions)} items, should be exactly 4"

    @pytest.mark.asyncio
    async def test_returns_all_required_fields(self):
        """Verify generate() returns all required fields."""
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
        """Verify language parameter is injected into prompt."""
        captured = {}
        async def fake_generate(messages, **kwargs):
            captured["prompt"] = messages[0]["content"]
            return _make_llm_response()
        with patch("app.services.autoconfig._llm_client") as mock_client:
            mock_client.generate = fake_generate
            await generate(["content"], "<html></html>", language="nl")
        assert "Dutch" in captured["prompt"], \
            "Language parameter should be injected into the prompt"


# ── extract_brand_color ───────────────────────────────────────────────────────

class TestExtractBrandColor:
    """Test extract_brand_color() functionality."""

    def test_extract_brand_color_meta_tag(self):
        html = '<head><meta name="theme-color" content="#4F46E5"></head>'
        assert extract_brand_color(html) == "#4F46E5"

    def test_extract_brand_color_reversed_attrs(self):
        html = '<head><meta content="#4F46E5" name="theme-color"></head>'
        assert extract_brand_color(html) == "#4F46E5"

    def test_extract_brand_color_css_var(self):
        html = "<html><head><style>:root { --primary: #1a73e8; }</style></head></html>"
        assert extract_brand_color(html) == "#1a73e8"

    def test_extract_brand_color_empty_html(self):
        assert extract_brand_color("") is None

    def test_extract_brand_color_not_found(self):
        html = "<html><body><p>No color information here.</p></body></html>"
        assert extract_brand_color(html) is None


# ── helpers ───────────────────────────────────────────────────────────────────

_VALID_PAYLOAD = {
    "name": "Acme Support Bot",
    "welcome_message": "Welcome to Acme! How can I help you today?",
    "system_prompt": "You are a helpful support assistant for Acme Inc.",
    "suggested_questions": [
        "What products do you offer?",
        "How do I track my order?",
        "What is your return policy?",
        "How do I contact support?",
    ],
    "fallback_message": "I'm sorry, I don't have information on that topic. Please contact support.",
}


# ── generate ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_returns_all_fields():
    mock_generate = AsyncMock(return_value=json.dumps(_VALID_PAYLOAD))

    with patch("app.services.autoconfig._llm_client") as mock_client:
        mock_client.generate = mock_generate
        result = await generate(["Some website content about Acme products."], "")

    assert isinstance(result, AutoConfigResult)
    assert result.name == "Acme Support Bot"
    assert result.welcome_message == "Welcome to Acme! How can I help you today?"
    assert isinstance(result.system_prompt, str) and len(result.system_prompt) > 0
    assert len(result.suggested_questions) == 4
    assert isinstance(result.fallback_message, str) and len(result.fallback_message) > 0
    assert result.brand_color is None


@pytest.mark.asyncio
async def test_generate_brand_color_from_html():
    mock_generate = AsyncMock(return_value=json.dumps(_VALID_PAYLOAD))
    homepage_html = '<head><meta name="theme-color" content="#FF5733"></head>'

    with patch("app.services.autoconfig._llm_client") as mock_client:
        mock_client.generate = mock_generate
        result = await generate(["content"], homepage_html)

    assert result.brand_color == "#FF5733"


@pytest.mark.asyncio
async def test_generate_retries_on_bad_json():
    mock_generate = AsyncMock(side_effect=["This is not JSON at all.", json.dumps(_VALID_PAYLOAD)])

    with patch("app.services.autoconfig._llm_client") as mock_client:
        mock_client.generate = mock_generate
        result = await generate(["content"], "")

    assert mock_generate.call_count == 2
    assert result.name == "Acme Support Bot"


@pytest.mark.asyncio
async def test_generate_raises_on_double_failure():
    mock_generate = AsyncMock(return_value="still not json { broken")

    with patch("app.services.autoconfig._llm_client") as mock_client:
        mock_client.generate = mock_generate
        with pytest.raises(RuntimeError, match="LLM returned invalid JSON after retry"):
            await generate(["content"], "")

    assert mock_generate.call_count == 2


@pytest.mark.asyncio
async def test_generate_empty_html_no_brand_color():
    mock_generate = AsyncMock(return_value=json.dumps(_VALID_PAYLOAD))

    with patch("app.services.autoconfig._llm_client") as mock_client:
        mock_client.generate = mock_generate
        result = await generate(["content"], "")

    assert result.brand_color is None
