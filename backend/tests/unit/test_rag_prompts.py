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
