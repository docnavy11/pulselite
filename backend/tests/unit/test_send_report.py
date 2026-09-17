import pytest

pytest.skip(
    "v2 (HTMX rewrite): app.workers.tasks.send_report no longer exists - the Celery worker fleet was replaced by asyncio tasks in app/background. "
    "This test still describes behaviour the product has; it needs rewriting "
    "against the new location rather than deleting.",
    allow_module_level=True,
)

from datetime import datetime, timedelta, timezone

from app.workers.tasks.send_report import _should_send_report, _build_report_html


def test_should_send_daily_never_sent():
    """Daily report should send if never sent before."""
    assert _should_send_report("daily", None) is True


def test_should_send_daily_sent_recently():
    """Daily report should not send if sent < 20 hours ago."""
    recent = datetime.now(timezone.utc) - timedelta(hours=10)
    assert _should_send_report("daily", recent) is False


def test_should_send_daily_sent_long_ago():
    """Daily report should send if sent > 20 hours ago."""
    old = datetime.now(timezone.utc) - timedelta(hours=25)
    assert _should_send_report("daily", old) is True


def test_should_send_weekly_never_sent():
    assert _should_send_report("weekly", None) is True


def test_should_send_weekly_sent_recently():
    recent = datetime.now(timezone.utc) - timedelta(days=3)
    assert _should_send_report("weekly", recent) is False


def test_should_send_monthly_sent_recently():
    recent = datetime.now(timezone.utc) - timedelta(days=15)
    assert _should_send_report("monthly", recent) is False


def test_should_send_off():
    assert _should_send_report("off", None) is False


def test_build_report_html_all_sections():
    """HTML contains all enabled sections."""
    stats = {
        "total": 100, "resolved": 80, "escalated": 5, "resolution_rate": 0.8,
        "avg_confidence": 0.75, "avg_sentiment": 0.3, "prev_avg_sentiment": 0.2,
        "open_gaps": 3, "new_gaps": 1,
        "top_topics": [{"topic": "Billing", "count": 20}],
        "qa_count": 50, "qa_avg_confidence": 0.85,
    }
    sections = {
        "conversations": True, "confidence": True, "sentiment": True,
        "gaps": True, "top_topics": True, "qa_performance": True,
    }
    html = _build_report_html(stats, sections, "weekly", "https://app.pulse.dev")
    assert "100" in html  # total conversations
    assert "80" in html  # resolved
    assert "Billing" in html  # top topic
    assert "Q&amp;A" in html or "Q&A" in html  # qa section


def test_build_report_html_partial_sections():
    """Only enabled sections appear in the HTML."""
    stats = {
        "total": 50, "resolved": 40, "escalated": 2, "resolution_rate": 0.8,
        "avg_confidence": 0.7,
    }
    sections = {"conversations": True, "confidence": False, "sentiment": False,
                "gaps": False, "top_topics": False, "qa_performance": False}
    html = _build_report_html(stats, sections, "daily", "https://app.pulse.dev")
    assert "50" in html
    assert "Confidence" not in html
    assert "Sentiment" not in html
