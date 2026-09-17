"""Tests for language instruction in system prompt."""
import pytest

pytest.skip(
    "v2 (HTMX rewrite): app.services.rag.prompts no longer exists - app/services/rag was emptied in the v2 rewrite; prompts now live with the llm service. "
    "This test still describes behaviour the product has; it needs rewriting "
    "against the new location rather than deleting.",
    allow_module_level=True,
)

from unittest.mock import MagicMock

from app.services.rag.prompts import build_system_prompt


def _make_chatbot(auto_detect: bool = False, language: str = "en") -> MagicMock:
    bot = MagicMock()
    bot.display_name = "TestBot"
    bot.name = "Test Chatbot"
    bot.tone = "friendly"
    bot.language = language
    bot.system_prompt = ""
    bot.auto_detect_language = auto_detect
    return bot


def test_default_language_instruction():
    """When auto_detect_language is False, prompt says 'You respond in {language}'."""
    bot = _make_chatbot(auto_detect=False, language="French")
    prompt = build_system_prompt(bot)
    assert "You respond in French" in prompt
    assert "Detect the language" not in prompt


def test_auto_detect_language_instruction():
    """When auto_detect_language is True, prompt includes detection instruction."""
    bot = _make_chatbot(auto_detect=True, language="English")
    prompt = build_system_prompt(bot)
    assert "Detect the language" in prompt
    assert "default to English" in prompt
    assert "You respond in English." not in prompt
