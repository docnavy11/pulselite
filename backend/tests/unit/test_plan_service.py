"""Tests for plan tier lookup service."""
from unittest.mock import patch, MagicMock

import pytest

from app.services.plan_service import get_plan_tier, get_plan_limits, has_feature


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
    "free": _make_tier("free", 1, 100, 2, 500_000, []),
    "growth": _make_tier("growth", 10, 10_000, 50, 10_000_000, ["intelligence", "reranking"]),
    "enterprise": _make_tier("enterprise", -1, -1, -1, -1, ["intelligence", "reranking", "email_reports"]),
}


def test_get_plan_tier_returns_matching_tier():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        tier = get_plan_tier("free")
        assert tier.slug == "free"
        assert tier.max_chatbots == 1


def test_get_plan_tier_unknown_slug_falls_back_to_enterprise():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        tier = get_plan_tier("nonexistent")
        assert tier.slug == "enterprise"


def test_get_plan_limits_returns_dict():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("free")
        assert limits["chatbots"] == 1
        assert limits["conversations"] == 100
        assert limits["knowledge_bases"] == 2
        assert limits["chars_indexed"] == 500_000


def test_get_plan_limits_unlimited():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("enterprise")
        assert limits["chatbots"] == -1
        assert limits["conversations"] == -1


def test_has_feature_returns_true_when_feature_in_plan():
    workspace = MagicMock()
    workspace.plan = "growth"
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        with patch("app.services.plan_service.is_self_hosted", return_value=False):
            assert has_feature(workspace, "intelligence") is True


def test_has_feature_returns_false_when_feature_not_in_plan():
    workspace = MagicMock()
    workspace.plan = "free"
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        with patch("app.services.plan_service.is_self_hosted", return_value=False):
            assert has_feature(workspace, "intelligence") is False


def test_has_feature_always_true_in_self_hosted():
    workspace = MagicMock()
    workspace.plan = "free"
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        with patch("app.services.plan_service.is_self_hosted", return_value=True):
            assert has_feature(workspace, "intelligence") is True
