# backend/tests/unit/test_autoconfig.py
"""Unit tests for app.services.autoconfig — pure LLM config generation."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.autoconfig import AutoConfigResult, extract_brand_color, generate


# ── extract_brand_color ───────────────────────────────────────────────────────

def test_extract_brand_color_meta_tag():
    html = '<head><meta name="theme-color" content="#4F46E5"></head>'
    assert extract_brand_color(html) == "#4F46E5"


def test_extract_brand_color_reversed_attrs():
    html = '<head><meta content="#4F46E5" name="theme-color"></head>'
    assert extract_brand_color(html) == "#4F46E5"


def test_extract_brand_color_css_var():
    html = "<html><head><style>:root { --primary: #1a73e8; }</style></head></html>"
    assert extract_brand_color(html) == "#1a73e8"


def test_extract_brand_color_empty_html():
    assert extract_brand_color("") is None


def test_extract_brand_color_not_found():
    html = "<html><body><p>No color information here.</p></body></html>"
    assert extract_brand_color(html) is None


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_mock_response(content: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    return mock_response


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
    mock_create = AsyncMock(return_value=_make_mock_response(json.dumps(_VALID_PAYLOAD)))

    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        mock_cls.return_value = mock_client

        result = await generate(["Some website content about Acme products."], "")

    assert isinstance(result, AutoConfigResult)
    assert result.name == "Acme Support Bot"
    assert result.welcome_message == "Welcome to Acme! How can I help you today?"
    assert isinstance(result.system_prompt, str) and len(result.system_prompt) > 0
    assert len(result.suggested_questions) == 4
    assert isinstance(result.fallback_message, str) and len(result.fallback_message) > 0


@pytest.mark.asyncio
async def test_generate_brand_color_from_html():
    mock_create = AsyncMock(return_value=_make_mock_response(json.dumps(_VALID_PAYLOAD)))
    homepage_html = '<head><meta name="theme-color" content="#FF5733"></head>'

    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        mock_cls.return_value = mock_client

        result = await generate(["content"], homepage_html)

    assert result.brand_color == "#FF5733"


@pytest.mark.asyncio
async def test_generate_retries_on_bad_json():
    bad_response = _make_mock_response("This is not JSON at all.")
    good_response = _make_mock_response(json.dumps(_VALID_PAYLOAD))
    mock_create = AsyncMock(side_effect=[bad_response, good_response])

    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        mock_cls.return_value = mock_client

        result = await generate(["content"], "")

    assert mock_create.call_count == 2
    assert result.name == "Acme Support Bot"


@pytest.mark.asyncio
async def test_generate_raises_on_double_failure():
    bad_response = _make_mock_response("still not json { broken")
    mock_create = AsyncMock(side_effect=[bad_response, bad_response])

    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        mock_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="LLM returned invalid JSON after retry"):
            await generate(["content"], "")

    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_generate_empty_html_no_brand_color():
    mock_create = AsyncMock(return_value=_make_mock_response(json.dumps(_VALID_PAYLOAD)))

    with patch("app.services.autoconfig.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        mock_cls.return_value = mock_client

        result = await generate(["content"], "")

    assert result.brand_color is None
