"""Unit tests for lead scoring regex logic (score_message_sync).

Signals and deltas from SCORING_RULES in score_lead.py:
  pricing      +15  r"\b(pricing|cost|how much|plans?|enterprise|subscription)\b"
  competitor   +10  r"\b(intercom|zendesk|chatbase|drift|freshdesk|helpscout)\b"
  urgency      +10  r"\b(asap|urgent|deadline|immediately|right away)\b"
  demo_request +20  r"\b(demo|trial|free trial|test|pilot|poc)\b"
  team_signal  +10  r"\b(my team|our company|we need|our organization)\b"
  negative     -15  r"\b(just browsing|homework|student|school project)\b"
"""
from app.workers.tasks.score_lead import score_message_sync


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

def test_returns_tuple_of_int_and_list():
    result = score_message_sync("test message")
    assert isinstance(result, tuple)
    score, signals = result
    assert isinstance(score, int)
    assert isinstance(signals, list)


# ---------------------------------------------------------------------------
# Zero / empty
# ---------------------------------------------------------------------------

def test_empty_message_scores_zero():
    score, signals = score_message_sync("")
    assert score == 0
    assert signals == []


def test_neutral_message_scores_zero():
    score, signals = score_message_sync("Hello, how can I get started?")
    assert score == 0
    assert signals == []


# ---------------------------------------------------------------------------
# Individual positive signals
# ---------------------------------------------------------------------------

def test_pricing_signal_keyword_pricing():
    score, signals = score_message_sync("What is your pricing for the enterprise plan?")
    assert score == 15
    assert "pricing" in signals


def test_pricing_signal_keyword_cost():
    score, signals = score_message_sync("I wanted to ask about the cost of your platform.")
    assert score == 15
    assert "pricing" in signals


def test_pricing_signal_keyword_enterprise():
    score, signals = score_message_sync("Do you offer an enterprise tier?")
    assert score == 15
    assert "pricing" in signals


def test_pricing_signal_keyword_subscription():
    score, signals = score_message_sync("How much does a monthly subscription cost?")
    # "subscription" → pricing (+15), "cost" also matches → still just one pricing label
    assert score >= 15
    assert "pricing" in signals


def test_competitor_mention_intercom():
    score, signals = score_message_sync("We currently use Intercom and want to switch.")
    assert score == 10
    assert "competitor" in signals


def test_competitor_mention_zendesk():
    score, signals = score_message_sync("We're evaluating Zendesk alternatives.")
    assert score == 10
    assert "competitor" in signals


def test_competitor_mention_chatbase():
    score, signals = score_message_sync("Chatbase doesn't support our use case.")
    assert score == 10
    assert "competitor" in signals


def test_urgency_signal_asap():
    # "we need" also triggers team_signal (+10), so total is 20
    score, signals = score_message_sync("I need this asap.")
    assert score == 10
    assert "urgency" in signals


def test_urgency_signal_deadline():
    score, signals = score_message_sync("We have a deadline next Friday.")
    assert score == 10
    assert "urgency" in signals


def test_urgency_signal_immediately():
    score, signals = score_message_sync("Can you help us immediately?")
    assert score == 10
    assert "urgency" in signals


def test_demo_request_keyword_demo():
    score, signals = score_message_sync("I'd like to book a demo with your team.")
    assert score == 20
    assert "demo_request" in signals


def test_demo_request_keyword_trial():
    score, signals = score_message_sync("Is there a free trial available?")
    assert score == 20
    assert "demo_request" in signals


def test_demo_request_keyword_poc():
    score, signals = score_message_sync("We want to run a POC before committing.")
    assert score == 20
    assert "demo_request" in signals


def test_demo_request_keyword_pilot():
    score, signals = score_message_sync("Can we start with a pilot program?")
    assert score == 20
    assert "demo_request" in signals


def test_team_signal_my_team():
    score, signals = score_message_sync("My team needs a better support solution.")
    assert score == 10
    assert "team_signal" in signals


def test_team_signal_our_company():
    score, signals = score_message_sync("Our company is looking for a chatbot platform.")
    assert score == 10
    assert "team_signal" in signals


def test_team_signal_we_need():
    score, signals = score_message_sync("We need an AI-native tool for customer support.")
    assert score == 10
    assert "team_signal" in signals


def test_team_signal_our_organization():
    score, signals = score_message_sync("Our organization has 200 support agents.")
    assert score == 10
    assert "team_signal" in signals


# ---------------------------------------------------------------------------
# Negative signal
# ---------------------------------------------------------------------------

def test_negative_signal_just_browsing():
    score, signals = score_message_sync("I'm just browsing, not looking to buy.")
    assert score == -15
    assert "negative" in signals


def test_negative_signal_student():
    score, signals = score_message_sync("I'm a student researching AI chatbots.")
    assert score == -15
    assert "negative" in signals


def test_negative_signal_school_project():
    score, signals = score_message_sync("This is for a school project.")
    assert score == -15
    assert "negative" in signals


def test_negative_signal_homework():
    score, signals = score_message_sync("I need this info for homework.")
    assert score == -15
    assert "negative" in signals


# ---------------------------------------------------------------------------
# Stacking / combinations
# ---------------------------------------------------------------------------

def test_pricing_and_urgency_stack():
    # pricing (+15) + urgency (+10) = 25
    score, signals = score_message_sync("I need pricing information asap.")
    assert score == 25
    assert "pricing" in signals
    assert "urgency" in signals


def test_demo_and_team_signal_stack():
    # demo_request (+20) + team_signal (+10) = 30
    score, signals = score_message_sync("My team would like to schedule a demo.")
    assert score == 30
    assert "demo_request" in signals
    assert "team_signal" in signals


def test_pricing_urgency_demo_stack():
    # pricing (+15) + urgency (+10) + demo_request (+20) = 45
    score, signals = score_message_sync(
        "I need pricing asap; can I schedule a demo this week?"
    )
    assert score == 45
    assert len(signals) == 3


def test_all_positive_signals_stack():
    # pricing (+15) + competitor (+10) + urgency (+10) + demo (+20) + team (+10) = 65
    msg = (
        "Our company is migrating from Intercom and we need pricing asap. "
        "Can we set up a demo or trial immediately?"
    )
    score, signals = score_message_sync(msg)
    assert score == 65
    assert len(signals) == 5


def test_positive_and_negative_cancel_partially():
    # demo_request (+20) + negative (-15) = 5
    score, signals = score_message_sync(
        "I'm a student but I'd like to see a demo for my research."
    )
    assert score == 5
    assert "demo_request" in signals
    assert "negative" in signals


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------

def test_signals_are_case_insensitive_upper():
    score_upper, signals_upper = score_message_sync("PRICING DEMO ASAP")
    score_lower, signals_lower = score_message_sync("pricing demo asap")
    assert score_upper == score_lower
    assert set(signals_upper) == set(signals_lower)


def test_signals_are_case_insensitive_mixed():
    score, signals = score_message_sync("What Is Your Pricing?")
    assert score == 15
    assert "pricing" in signals


# ---------------------------------------------------------------------------
# Word-boundary enforcement (no partial matches)
# ---------------------------------------------------------------------------

def test_no_partial_match_for_pricing():
    # "repricing" should not trigger pricing signal
    _, signals = score_message_sync("We are repricing our internal products.")
    assert "pricing" not in signals


def test_no_partial_match_for_urgency():
    # "urgency" alone is a match, but "urgencies" (with word boundary broken by 'ies') should not
    _, signals = score_message_sync("We have many urgencies to address.")
    assert "urgency" not in signals
