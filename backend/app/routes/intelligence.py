"""Intelligence routes — gaps, sentiment, retrieval logs."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.intelligence import ConversationAnalysis, GapCluster, GapEvent, RetrievalLog

router = APIRouter(prefix="/intelligence")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def intelligence_overview(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    ws_id = workspace.id

    gap_count = (await db.execute(
        select(func.count(GapCluster.id)).where(GapCluster.workspace_id == ws_id, GapCluster.status == "open")
    )).scalar_one()

    recent_retrievals = (await db.execute(
        select(func.count(RetrievalLog.id)).where(
            RetrievalLog.workspace_id == ws_id,
            RetrievalLog.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
        )
    )).scalar_one()

    escalation_count = (await db.execute(
        select(func.count(RetrievalLog.id)).where(
            RetrievalLog.workspace_id == ws_id, RetrievalLog.escalated == True,
            RetrievalLog.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
        )
    )).scalar_one()

    return request.app.state.templates.TemplateResponse("intelligence/index.html", {
        "request": request, "gap_count": gap_count,
        "recent_retrievals": recent_retrievals, "escalation_count": escalation_count,
    })


@router.get("/gaps", response_class=HTMLResponse)
async def gap_list(request: Request, status: str | None = None, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    query = select(GapCluster).where(GapCluster.workspace_id == workspace.id)
    if status:
        query = query.where(GapCluster.status == status)
    clusters = (await db.execute(
        query.order_by(GapCluster.gap_count.desc()).limit(50)
    )).scalars().all()
    return request.app.state.templates.TemplateResponse("intelligence/gaps.html", {
        "request": request, "clusters": clusters,
    })


@router.get("/gaps/{cluster_id}", response_class=HTMLResponse)
async def gap_detail(request: Request, cluster_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    cluster = (await db.execute(
        select(GapCluster).where(GapCluster.id == cluster_id, GapCluster.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if not cluster:
        return HTMLResponse("Not found", status_code=404)
    events = (await db.execute(
        select(GapEvent).where(GapEvent.gap_cluster_id == cluster_id).order_by(GapEvent.created_at.desc()).limit(50)
    )).scalars().all()
    return request.app.state.templates.TemplateResponse("intelligence/gap_detail.html", {
        "request": request, "cluster": cluster, "events": events,
    })


@router.post("/gaps/{cluster_id}/dismiss")
async def dismiss_gap(request: Request, cluster_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    cluster = (await db.execute(
        select(GapCluster).where(GapCluster.id == cluster_id, GapCluster.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if cluster:
        cluster.status = "dismissed"
        cluster.resolved_at = datetime.now(timezone.utc)
        await db.flush()
    return HTMLResponse('<div id="gap-actions" class="mb-6"><span class="text-sm text-gray-400">Dismissed</span></div>')


@router.post("/gaps/{cluster_id}/approve")
async def approve_gap(request: Request, cluster_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    cluster = (await db.execute(
        select(GapCluster).where(GapCluster.id == cluster_id, GapCluster.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if cluster:
        cluster.status = "approved"
        cluster.resolved_at = datetime.now(timezone.utc)
        await db.flush()
    return HTMLResponse('<div id="gap-actions" class="mb-6"><span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-50 border border-green-200 text-sm text-green-700"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>Approved</span></div>')


@router.get("/sentiment", response_class=HTMLResponse)
async def sentiment_view(request: Request, range: str = "30d", db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    days_map = {"7d": 7, "90d": 90}
    days = days_map.get(range, 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc("day", ConversationAnalysis.created_at).label("day"),
            func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
            func.count(ConversationAnalysis.id).label("count"),
        ).where(
            ConversationAnalysis.workspace_id == workspace.id,
            ConversationAnalysis.created_at >= cutoff,
            ConversationAnalysis.sentiment_score.isnot(None),
        ).group_by("day").order_by("day")
    )
    rows = result.all()
    trends = [{"date": row.day.strftime("%b %d"), "avg": round(float(row.avg_sentiment), 2), "count": row.count} for row in rows]

    scores = [t["avg"] for t in trends]
    avg_sentiment = round(sum(scores) / len(scores), 3) if scores else 0.0
    positive_pct = round(len([s for s in scores if s >= 0.3]) / len(scores) * 100) if scores else 0
    negative_pct = round(len([s for s in scores if s <= -0.3]) / len(scores) * 100) if scores else 0
    trend = round(scores[-1] - scores[0], 3) if len(scores) >= 2 else 0.0

    return request.app.state.templates.TemplateResponse("intelligence/sentiment.html", {
        "request": request, "trends": trends, "range": range, "days": days,
        "avg_sentiment": avg_sentiment, "positive_pct": positive_pct,
        "negative_pct": negative_pct, "trend": trend,
    })


@router.get("/sentiment/segment", response_class=HTMLResponse)
async def sentiment_segment(request: Request, segment: str = "chatbot", days: int = 30, db: AsyncSession = Depends(get_db)):
    from app.models.conversations import Conversation
    from app.models.organizational import Chatbot
    workspace = request.state.workspace
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if segment == "chatbot":
        result = await db.execute(
            select(
                Chatbot.name,
                func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
                func.count().label("count"),
            )
            .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            .join(Chatbot, Chatbot.id == Conversation.chatbot_id)
            .where(
                ConversationAnalysis.workspace_id == workspace.id,
                ConversationAnalysis.sentiment_score.isnot(None),
                ConversationAnalysis.created_at >= cutoff,
            )
            .group_by(Chatbot.id, Chatbot.name)
            .order_by(func.count().desc())
            .limit(20)
        )
    else:
        from app.models.conversations import Contact
        result = await db.execute(
            select(
                func.coalesce(Contact.name, Contact.email, "Anonymous").label("name"),
                func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
                func.count().label("count"),
            )
            .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            .join(Contact, Contact.id == Conversation.contact_id)
            .where(
                ConversationAnalysis.workspace_id == workspace.id,
                ConversationAnalysis.sentiment_score.isnot(None),
                ConversationAnalysis.created_at >= cutoff,
            )
            .group_by(Contact.id, Contact.name, Contact.email)
            .order_by(func.count().desc())
            .limit(10)
        )

    segment_data = [
        {"name": row.name, "avg_sentiment": round(float(row.avg_sentiment), 3), "count": row.count}
        for row in result.all()
    ]
    return request.app.state.templates.TemplateResponse("intelligence/_sentiment_segment.html", {
        "request": request, "segment_data": segment_data,
    })


@router.post("/trigger/analyze-all")
async def trigger_analyze_all(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from app.models.conversations import Conversation
    from app.background.runner import submit_job
    convs = (await db.execute(
        select(Conversation.id).where(Conversation.workspace_id == workspace.id, Conversation.status == "closed")
        .limit(100)
    )).all()
    for (conv_id,) in convs:
        await submit_job("analyze_conversation", {"conversation_id": str(conv_id), "workspace_id": str(workspace.id)})
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": f"Queued {len(convs)} conversations for analysis", "type": "success",
        })
    return RedirectResponse("/intelligence", status_code=303)


@router.post("/trigger/sentiment-trends")
async def trigger_sentiment(request: Request, db: AsyncSession = Depends(get_db)):
    from app.background.runner import submit_job
    await submit_job("compute_sentiment_trends")
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Sentiment trend computation started", "type": "success",
        })
    return RedirectResponse("/intelligence/sentiment", status_code=303)


@router.post("/trigger/cluster-gaps")
async def trigger_cluster(request: Request, db: AsyncSession = Depends(get_db)):
    from app.background.runner import submit_job
    await submit_job("cluster_gaps")
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Gap clustering started", "type": "success",
        })
    return RedirectResponse("/intelligence/gaps", status_code=303)
