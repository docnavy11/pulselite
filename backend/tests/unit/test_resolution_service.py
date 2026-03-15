import pytest


class TestIsSubstantiveQuery:
    def test_greeting_is_not_substantive(self):
        from app.services.resolution_service import _is_substantive_query
        assert _is_substantive_query("hello") is False
        assert _is_substantive_query("Hi!") is False
        assert _is_substantive_query("hey") is False

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
