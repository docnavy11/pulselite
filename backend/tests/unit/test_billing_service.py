"""Unit tests for plan limits via plan_service."""
from unittest.mock import patch, MagicMock

from app.services.plan_service import get_plan_limits


def _make_tier(slug, max_chatbots=1, max_conversations=-1, max_knowledge_bases=2,
               max_chars_indexed=500_000, features=None):
    tier = MagicMock()
    tier.slug = slug
    tier.max_chatbots = max_chatbots
    tier.max_conversations_monthly = max_conversations
    tier.max_knowledge_bases = max_knowledge_bases
    tier.max_chars_indexed = max_chars_indexed
    tier.features = features or []
    return tier


FAKE_CACHE = {
    "free": _make_tier("free", 1, 100, 2, 500_000),
    "starter": _make_tier("starter", 3, 1000, 10, 2_000_000),
    "growth": _make_tier("growth", 10, 10_000, 50, 10_000_000),
    "professional": _make_tier("professional", 10, 10_000, 50, 10_000_000),
    "agency": _make_tier("agency", 50, 50_000, 200, -1),
    "enterprise": _make_tier("enterprise", -1, -1, -1, -1),
}


def test_free_plan_limits():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("free")
        assert limits["conversations"] == 100
        assert limits["chatbots"] == 1
        assert limits["knowledge_bases"] == 2


def test_starter_plan_limits():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("starter")
        assert limits["conversations"] == 1000
        assert limits["chatbots"] == 3
        assert limits["knowledge_bases"] == 10


def test_growth_plan_limits():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("growth")
        assert limits["conversations"] == 10_000
        assert limits["chatbots"] == 10
        assert limits["knowledge_bases"] == 50


def test_agency_plan_limits():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("agency")
        assert limits["conversations"] == 50_000
        assert limits["chatbots"] == 50
        assert limits["knowledge_bases"] == 200


def test_enterprise_plan_unlimited():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("enterprise")
        assert limits["conversations"] == -1
        assert limits["chatbots"] == -1
        assert limits["knowledge_bases"] == -1


def test_returns_dict_with_required_keys():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        for plan in ("free", "starter", "growth", "agency", "enterprise"):
            limits = get_plan_limits(plan)
            assert isinstance(limits, dict)
            for key in ("conversations", "chatbots", "knowledge_bases", "chars_indexed"):
                assert key in limits


def test_starter_conversations_exceed_free():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        assert get_plan_limits("starter")["conversations"] > get_plan_limits("free")["conversations"]


def test_growth_conversations_exceed_starter():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        assert get_plan_limits("growth")["conversations"] > get_plan_limits("starter")["conversations"]


def test_agency_conversations_exceed_growth():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        assert get_plan_limits("agency")["conversations"] > get_plan_limits("growth")["conversations"]


def test_unknown_plan_falls_back_to_enterprise():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("nonexistent_plan")
        assert limits["conversations"] == -1
        assert limits["chatbots"] == -1
