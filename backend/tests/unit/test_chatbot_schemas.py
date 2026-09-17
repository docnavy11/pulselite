"""Unit tests for chatbot schema validation."""
import pytest

pytest.skip(
    "v2 (HTMX rewrite): app.schemas.chatbots no longer exists - app/schemas went with the JSON API in the v2 rewrite - HTMX renders templates, so there are no response schemas to assert on. "
    "This test still describes behaviour the product has; it needs rewriting "
    "against the new location rather than deleting.",
    allow_module_level=True,
)

import uuid
import pytest
from pydantic import ValidationError
from app.schemas.chatbots import ChatbotUpdate, CrawlProgressResponse


class TestChatbotUpdateSetupStatus:
    def test_done_is_accepted(self):
        u = ChatbotUpdate(setup_status="done")
        assert u.setup_status == "done"

    def test_crawling_is_rejected(self):
        with pytest.raises(ValidationError):
            ChatbotUpdate(setup_status="crawling")

    def test_configuring_is_rejected(self):
        with pytest.raises(ValidationError):
            ChatbotUpdate(setup_status="configuring")

    def test_none_is_accepted(self):
        u = ChatbotUpdate(setup_status=None)
        assert u.setup_status is None

    def test_omitted_is_none(self):
        u = ChatbotUpdate()
        assert u.setup_status is None


class TestCrawlProgressResponse:
    def test_fields_present(self):
        p = CrawlProgressResponse(
            pages_queued=12,
            pages_discovered=34,
            status="running",
            error_message=None,
        )
        assert p.pages_queued == 12
        assert p.pages_discovered == 34
        assert p.status == "running"
        assert p.error_message is None
