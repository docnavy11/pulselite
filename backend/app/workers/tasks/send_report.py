import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import func, select

from app.database import async_session_factory, engine
from app.models.conversations import Conversation
from app.models.intelligence import ConversationAnalysis, GapCluster
from app.models.organizational import Workspace
from app.services.integrations.email import _get_email_config, send_email
from app.services.integrations.slack import send_weekly_digest
from app.services.realtime import emit_task_event
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Minimum intervals to avoid double-sending (with buffer)
_MIN_INTERVALS = {
    "daily": timedelta(hours=20),
    "weekly": timedelta(days=6),
    "monthly": timedelta(days=27),
}

_PERIOD_DAYS = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
}

_PERIOD_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
}


def _should_send_report(frequency: str, last_sent: datetime | None) -> bool:
    """Check whether it's time to send a report."""
    if frequency not in _MIN_INTERVALS:
        return False
    if last_sent is None:
        return True
    elapsed = datetime.now(timezone.utc) - last_sent
    return elapsed >= _MIN_INTERVALS[frequency]


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=110, time_limit=120)
def send_report_task(self) -> dict:
    try:
        return asyncio.run(_send_reports(self.request.id))
    except MaxRetriesExceededError:
        logger.error("send_report_task failed after max retries")
        return {"status": "failed", "reason": "max retries exceeded"}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _send_reports(task_id: str) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                select(Workspace.id, Workspace.intelligence_config, Workspace.last_report_sent_at)
            )
            workspaces = result.all()

            sent = 0
            for ws_id, intel_config, last_sent in workspaces:
                config = intel_config or {}
                frequency = config.get("report_frequency", "off")

                if not _should_send_report(frequency, last_sent):
                    continue

                try:
                    await emit_task_event(ws_id, "started", "send_report", task_id)

                    recipients = config.get("report_recipients", [])
                    sections = config.get("report_sections", {})
                    # Default all sections to True
                    for key in ("conversations", "confidence", "sentiment", "gaps", "top_topics", "qa_performance"):
                        sections.setdefault(key, True)

                    period_days = _PERIOD_DAYS[frequency]
                    stats = await _compute_stats(session, ws_id, period_days)

                    email_config = await _get_email_config(session, ws_id)
                    app_url = (email_config or {}).get("app_url", "http://localhost:3000")
                    html = _build_report_html(stats, sections, frequency, app_url)
                    subject = f"Pulse {_PERIOD_LABELS[frequency]} Report"

                    # Send to configured recipients or fall back to email integration to_email
                    if email_config:
                        if recipients:
                            for recipient in recipients:
                                cfg_copy = {**email_config, "to_email": recipient}
                                send_email(cfg_copy, subject, html)
                        else:
                            send_email(email_config, subject, html)
                        sent += 1

                    # Also send Slack digest for weekly (backwards compat)
                    if frequency == "weekly":
                        await send_weekly_digest(session, ws_id, stats)

                    # Update last_report_sent_at
                    ws_result = await session.execute(select(Workspace).where(Workspace.id == ws_id))
                    ws = ws_result.scalar_one()
                    ws.last_report_sent_at = datetime.now(timezone.utc)
                    await session.commit()

                    await emit_task_event(ws_id, "completed", "send_report", task_id)
                except Exception:
                    logger.exception(f"Report send failed for workspace {ws_id}")
                    await session.rollback()
                    await emit_task_event(ws_id, "completed", "send_report", task_id, error="Report send failed")

            return {"status": "success", "reports_sent": sent}
        except Exception:
            logger.exception("Report send failed")
            raise


async def _compute_stats(session, workspace_id: uuid.UUID, period_days: int) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=period_days)
    prev_cutoff = cutoff - timedelta(days=period_days)

    # Conversations
    total_result = await session.execute(
        select(func.count()).select_from(Conversation).where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= cutoff,
        )
    )
    total = total_result.scalar() or 0

    resolved_result = await session.execute(
        select(func.count()).select_from(Conversation).where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= cutoff,
            Conversation.autonomous_resolved == True,  # noqa: E712
        )
    )
    resolved = resolved_result.scalar() or 0

    escalated_result = await session.execute(
        select(func.count()).select_from(Conversation).where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= cutoff,
            Conversation.escalation_reason.isnot(None),
        )
    )
    escalated = escalated_result.scalar() or 0

    resolution_rate = resolved / total if total > 0 else 0.0

    # Confidence
    confidence_result = await session.execute(
        select(func.avg(Conversation.confidence_avg)).where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= cutoff,
            Conversation.confidence_avg.isnot(None),
        )
    )
    avg_confidence = confidence_result.scalar() or 0.0

    # Sentiment (current + previous period for trend)
    sentiment_result = await session.execute(
        select(func.avg(ConversationAnalysis.sentiment_score)).where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.created_at >= cutoff,
            ConversationAnalysis.sentiment_score.isnot(None),
        )
    )
    avg_sentiment = sentiment_result.scalar()

    prev_sentiment_result = await session.execute(
        select(func.avg(ConversationAnalysis.sentiment_score)).where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.created_at >= prev_cutoff,
            ConversationAnalysis.created_at < cutoff,
            ConversationAnalysis.sentiment_score.isnot(None),
        )
    )
    prev_avg_sentiment = prev_sentiment_result.scalar()

    # Gaps
    open_gaps_result = await session.execute(
        select(func.count()).select_from(GapCluster).where(
            GapCluster.workspace_id == workspace_id, GapCluster.status == "open"
        )
    )
    open_gaps = open_gaps_result.scalar() or 0

    new_gaps_result = await session.execute(
        select(func.count()).select_from(GapCluster).where(
            GapCluster.workspace_id == workspace_id,
            GapCluster.status == "open",
            GapCluster.created_at >= cutoff,
        )
    )
    new_gaps = new_gaps_result.scalar() or 0

    # Top topics
    top_topics_result = await session.execute(
        select(
            func.unnest(ConversationAnalysis.topics).label("topic"),
            func.count().label("cnt"),
        )
        .where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.created_at >= cutoff,
        )
        .group_by("topic")
        .order_by(func.count().desc())
        .limit(5)
    )
    top_topics = [{"topic": row[0], "count": row[1]} for row in top_topics_result.all()]

    # Q&A performance
    qa_count = 0
    qa_avg_confidence = None
    try:
        from app.models.qa import QAPair

        qa_count_result = await session.execute(
            select(func.count()).select_from(QAPair).where(QAPair.workspace_id == workspace_id)
        )
        qa_count = qa_count_result.scalar() or 0
        if qa_count > 0:
            qa_conf_result = await session.execute(
                select(func.avg(QAPair.confidence_score)).where(
                    QAPair.workspace_id == workspace_id,
                    QAPair.confidence_score.isnot(None),
                )
            )
            qa_avg_confidence = qa_conf_result.scalar()
    except Exception:
        pass  # QAPair table may not exist yet

    return {
        "total": total,
        "resolved": resolved,
        "escalated": escalated,
        "resolution_rate": resolution_rate,
        "avg_confidence": round(float(avg_confidence), 3),
        "avg_sentiment": round(float(avg_sentiment), 3) if avg_sentiment is not None else None,
        "prev_avg_sentiment": round(float(prev_avg_sentiment), 3) if prev_avg_sentiment is not None else None,
        "open_gaps": open_gaps,
        "new_gaps": new_gaps,
        "top_topics": top_topics,
        "qa_count": qa_count,
        "qa_avg_confidence": round(float(qa_avg_confidence), 3) if qa_avg_confidence is not None else None,
    }


def _build_report_html(stats: dict, sections: dict, frequency: str, app_url: str) -> str:
    """Build the HTML email body with only enabled sections."""
    period_label = _PERIOD_LABELS.get(frequency, "Weekly")
    parts = [
        f'<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto;">',
        f'<h2 style="color: #1a1a1a;">Pulse {period_label} Report</h2>',
    ]

    if sections.get("conversations"):
        rate_pct = f"{stats.get('resolution_rate', 0):.0%}"
        parts.append(f"""
        <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h3 style="margin: 0 0 12px; color: #374151; font-size: 14px;">Conversations</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 8px; color: #6b7280;">Total</td><td style="padding: 4px 8px; font-weight: 600;">{stats.get('total', 0)}</td></tr>
                <tr><td style="padding: 4px 8px; color: #6b7280;">Resolved</td><td style="padding: 4px 8px; font-weight: 600;">{stats.get('resolved', 0)}</td></tr>
                <tr><td style="padding: 4px 8px; color: #6b7280;">Escalated</td><td style="padding: 4px 8px; font-weight: 600;">{stats.get('escalated', 0)}</td></tr>
                <tr><td style="padding: 4px 8px; color: #6b7280;">Resolution Rate</td><td style="padding: 4px 8px; font-weight: 600;">{rate_pct}</td></tr>
            </table>
        </div>
        """)

    if sections.get("confidence"):
        parts.append(f"""
        <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h3 style="margin: 0 0 8px; color: #374151; font-size: 14px;">Confidence</h3>
            <p style="margin: 0; font-size: 24px; font-weight: 600;">{stats.get('avg_confidence', 0):.2f}</p>
        </div>
        """)

    if sections.get("sentiment"):
        sentiment_val = stats.get("avg_sentiment")
        prev_val = stats.get("prev_avg_sentiment")
        trend = ""
        if sentiment_val is not None and prev_val is not None:
            diff = sentiment_val - prev_val
            arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
            trend = f' <span style="color: {"#10b981" if diff >= 0 else "#ef4444"};">{arrow} {abs(diff):.2f}</span>'
        parts.append(f"""
        <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h3 style="margin: 0 0 8px; color: #374151; font-size: 14px;">Sentiment</h3>
            <p style="margin: 0; font-size: 24px; font-weight: 600;">{sentiment_val if sentiment_val is not None else "N/A"}{trend}</p>
        </div>
        """)

    if sections.get("gaps"):
        parts.append(f"""
        <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h3 style="margin: 0 0 8px; color: #374151; font-size: 14px;">Knowledge Gaps</h3>
            <p style="margin: 0;"><strong>{stats.get('open_gaps', 0)}</strong> open clusters, <strong>{stats.get('new_gaps', 0)}</strong> new this period</p>
        </div>
        """)

    if sections.get("top_topics") and stats.get("top_topics"):
        topics_html = "".join(
            f'<li style="padding: 4px 0;">{t["topic"]} ({t["count"]})</li>'
            for t in stats["top_topics"]
        )
        parts.append(f"""
        <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h3 style="margin: 0 0 8px; color: #374151; font-size: 14px;">Top Topics</h3>
            <ol style="margin: 0; padding-left: 20px;">{topics_html}</ol>
        </div>
        """)

    if sections.get("qa_performance") and stats.get("qa_count", 0) > 0:
        qa_conf = stats.get("qa_avg_confidence")
        qa_conf_str = f"{qa_conf:.2f}" if qa_conf is not None else "N/A"
        parts.append(f"""
        <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h3 style="margin: 0 0 8px; color: #374151; font-size: 14px;">Q&amp;A Performance</h3>
            <p style="margin: 0;"><strong>{stats['qa_count']}</strong> pairs, avg confidence: <strong>{qa_conf_str}</strong></p>
        </div>
        """)

    parts.append(f"""
    <p style="margin-top: 24px; color: #9ca3af; font-size: 12px;">
        <a href="{app_url}/dashboard" style="color: #6366f1;">View Dashboard</a> · Sent by Pulse
    </p>
    </div>
    """)

    return "\n".join(parts)
