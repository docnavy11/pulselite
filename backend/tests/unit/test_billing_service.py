"""Unit tests for app.services.billing — plan limits."""
from app.services.billing import get_plan_limits, PLAN_LIMITS


# ---------------------------------------------------------------------------
# get_plan_limits — return value correctness
# ---------------------------------------------------------------------------

def test_free_plan_limits():
    limits = get_plan_limits("free")
    assert limits["conversations"] == 100
    assert limits["chatbots"] == 1
    assert limits["knowledge_bases"] == 2


def test_starter_plan_limits():
    limits = get_plan_limits("starter")
    assert limits["conversations"] == 1000
    assert limits["chatbots"] == 3
    assert limits["knowledge_bases"] == 10


def test_professional_plan_limits():
    limits = get_plan_limits("professional")
    assert limits["conversations"] == 10000
    assert limits["chatbots"] == 10
    assert limits["knowledge_bases"] == 50


def test_agency_plan_limits():
    limits = get_plan_limits("agency")
    assert limits["conversations"] == 50000
    assert limits["chatbots"] == 50
    assert limits["knowledge_bases"] == 200


def test_enterprise_plan_unlimited():
    limits = get_plan_limits("enterprise")
    # -1 signals unlimited for all dimensions
    assert limits["conversations"] == -1
    assert limits["chatbots"] == -1
    assert limits["knowledge_bases"] == -1


# ---------------------------------------------------------------------------
# Type / shape guarantees
# ---------------------------------------------------------------------------

def test_returns_dict_with_required_keys():
    for plan in ("free", "starter", "professional", "agency", "enterprise"):
        limits = get_plan_limits(plan)
        assert isinstance(limits, dict), f"Expected dict for plan '{plan}'"
        for key in ("conversations", "chatbots", "knowledge_bases"):
            assert key in limits, f"Key '{key}' missing for plan '{plan}'"


# ---------------------------------------------------------------------------
# Ordering: paid tiers must exceed free (except enterprise which uses -1)
# ---------------------------------------------------------------------------

def test_starter_conversations_exceed_free():
    assert get_plan_limits("starter")["conversations"] > get_plan_limits("free")["conversations"]


def test_professional_conversations_exceed_starter():
    assert get_plan_limits("professional")["conversations"] > get_plan_limits("starter")["conversations"]


def test_agency_conversations_exceed_professional():
    assert get_plan_limits("agency")["conversations"] > get_plan_limits("professional")["conversations"]


def test_chatbot_limits_increase_by_tier():
    free = get_plan_limits("free")["chatbots"]
    starter = get_plan_limits("starter")["chatbots"]
    professional = get_plan_limits("professional")["chatbots"]
    agency = get_plan_limits("agency")["chatbots"]
    assert free < starter < professional < agency


def test_knowledge_base_limits_increase_by_tier():
    free = get_plan_limits("free")["knowledge_bases"]
    starter = get_plan_limits("starter")["knowledge_bases"]
    professional = get_plan_limits("professional")["knowledge_bases"]
    agency = get_plan_limits("agency")["knowledge_bases"]
    assert free < starter < professional < agency


# ---------------------------------------------------------------------------
# Unknown plan falls back to free
# ---------------------------------------------------------------------------

def test_unknown_plan_falls_back_to_free():
    limits = get_plan_limits("nonexistent_plan")
    free_limits = get_plan_limits("free")
    assert limits == free_limits


# ---------------------------------------------------------------------------
# PLAN_LIMITS dict covers all expected plans
# ---------------------------------------------------------------------------

def test_all_expected_plans_present_in_plan_limits():
    expected_plans = {"free", "starter", "professional", "agency", "enterprise"}
    assert expected_plans.issubset(set(PLAN_LIMITS.keys()))
