"""Chatbot routes — list, create, detail, update, delete, widget config."""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.knowledge import Chatbot, KnowledgeBase, Document

router = APIRouter()


@router.get("/chatbots", response_class=HTMLResponse)
async def list_chatbots(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(
        select(Chatbot).where(Chatbot.workspace_id == workspace.id, Chatbot.archived_at.is_(None))
        .order_by(Chatbot.created_at.desc())
    )
    chatbots = result.scalars().all()

    # Fetch per-chatbot stats
    from datetime import datetime, timedelta, timezone
    from app.models.conversations import Conversation
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    stats = {}
    for bot in chatbots:
        conv_count = (await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.chatbot_id == bot.id, Conversation.created_at >= thirty_days_ago
            )
        )).scalar_one()
        resolved_count = (await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.chatbot_id == bot.id, Conversation.autonomous_resolved == True
            )
        )).scalar_one()
        total = (await db.execute(
            select(func.count(Conversation.id)).where(Conversation.chatbot_id == bot.id)
        )).scalar_one()
        last_active_result = await db.execute(
            select(func.max(Conversation.created_at)).where(Conversation.chatbot_id == bot.id)
        )
        last_active = last_active_result.scalar_one()

        stats[str(bot.id)] = {
            "conversations_30d": conv_count,
            "resolution_rate": round(resolved_count / total * 100) if total > 0 else 0,
            "last_active": last_active,
        }

    # Check if crawl jobs are active
    from app.models.knowledge import CrawlJob
    active_crawls = {}
    for bot in chatbots:
        if bot.active_crawl_job_id:
            crawl_result = await db.execute(select(CrawlJob).where(CrawlJob.id == bot.active_crawl_job_id))
            crawl = crawl_result.scalar_one_or_none()
            if crawl:
                active_crawls[str(bot.id)] = crawl

    return request.app.state.templates.TemplateResponse("chatbots/list.html", {
        "request": request, "chatbots": chatbots, "stats": stats, "active_crawls": active_crawls,
    })


@router.get("/chatbots/new", response_class=HTMLResponse)
async def new_chatbot_page(request: Request):
    return request.app.state.templates.TemplateResponse("chatbots/new.html", {"request": request})


@router.post("/chatbots")
async def create_chatbot(
    request: Request, name: str = Form("My Support Bot"), url: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    chatbot = Chatbot(workspace_id=workspace.id, name=name or "My Support Bot")
    db.add(chatbot)
    await db.flush()

    if url:
        from app.services.crawl_service import prepare_crawl
        from app.background.runner import submit_job
        job_id, kb_id = await prepare_crawl(db, workspace.id, url, chatbot_id=chatbot.id)
        await submit_job("crawl_website", {"job_id": job_id})

    await db.commit()
    # If URL provided go to wizard setup, otherwise straight to chatbot detail
    if url:
        return RedirectResponse(f"/chatbots/{chatbot.id}/setup", status_code=303)
    return RedirectResponse(f"/chatbots/{chatbot.id}", status_code=303)


@router.get("/chatbots/{chatbot_id}/setup", response_class=HTMLResponse)
async def chatbot_setup(request: Request, chatbot_id: uuid.UUID, step: int = 0, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    chatbot = (await db.execute(
        select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)

    # step=4 query param means review was just saved → show deploy step
    if step == 4:
        return request.app.state.templates.TemplateResponse("chatbots/setup.html", {
            "request": request, "chatbot": chatbot, "crawl_job": None,
            "app_url": str(request.base_url).rstrip("/"),
            "force_step": 4,
        })

    # If already done but no step=4 param, redirect to chatbot detail
    if chatbot.setup_status == "done":
        return RedirectResponse(f"/chatbots/{chatbot_id}", status_code=303)

    # Load crawl job if active
    crawl_job = None
    if chatbot.active_crawl_job_id:
        from app.models.knowledge import CrawlJob
        crawl_job = (await db.execute(
            select(CrawlJob).where(CrawlJob.id == chatbot.active_crawl_job_id)
        )).scalar_one_or_none()

    return request.app.state.templates.TemplateResponse("chatbots/setup.html", {
        "request": request, "chatbot": chatbot, "crawl_job": crawl_job,
        "app_url": str(request.base_url).rstrip("/"),
    })


@router.get("/chatbots/{chatbot_id}/setup/progress", response_class=HTMLResponse)
async def setup_progress(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Polled every 2s during step 2. Returns updated progress HTML, or triggers redirect when ready."""
    workspace = request.state.workspace
    chatbot = (await db.execute(
        select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("")

    # Transition to step 3 (review) or step 4 (done)
    if chatbot.setup_status in ("ready", "done"):
        from fastapi.responses import Response
        r = Response("")
        r.headers["HX-Redirect"] = f"/chatbots/{chatbot_id}/setup"
        return r

    crawl_job = None
    if chatbot.active_crawl_job_id:
        from app.models.knowledge import CrawlJob
        crawl_job = (await db.execute(
            select(CrawlJob).where(CrawlJob.id == chatbot.active_crawl_job_id)
        )).scalar_one_or_none()

    return request.app.state.templates.TemplateResponse("chatbots/_setup_progress.html", {
        "request": request, "chatbot": chatbot, "crawl_job": crawl_job,
    })


@router.post("/chatbots/{chatbot_id}/setup/review", response_class=HTMLResponse)
async def setup_review_save(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Save step 3 review form and advance to step 4."""
    workspace = request.state.workspace
    chatbot = (await db.execute(
        select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)

    form = await request.form()
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(Chatbot).where(Chatbot.id == chatbot_id).values(
            name=form.get("name", chatbot.name),
            welcome_message=form.get("welcome_message", chatbot.welcome_message),
            system_prompt=form.get("system_prompt", chatbot.system_prompt),
            fallback_message=form.get("fallback_message", chatbot.fallback_message),
            tone=form.get("tone", chatbot.tone or "professional"),
            language=form.get("language", chatbot.language or "en"),
            auto_detect_language=form.get("auto_detect_language") == "on",
            brand_color=form.get("brand_color", chatbot.brand_color or "#ff6b35"),
            setup_status="done",
        )
    )
    await db.commit()
    return RedirectResponse(f"/chatbots/{chatbot_id}/setup?step=4", status_code=303)




@router.get("/chatbots/{chatbot_id}", response_class=HTMLResponse)
async def chatbot_detail(request: Request, chatbot_id: uuid.UUID, days: int = 30, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(
        select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id)
    )
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)

    # Redirect to setup wizard if still being set up
    if chatbot.setup_status in ("crawling", "configuring", "ready", "setup_failed"):
        return RedirectResponse(f"/chatbots/{chatbot_id}/setup", status_code=303)

    from datetime import datetime, timedelta, timezone
    from app.models.conversations import Conversation, MessageFeedback
    from app.models.intelligence import ConversationAnalysis, GapCluster

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Conversations
    total = (await db.execute(select(func.count(Conversation.id)).where(
        Conversation.chatbot_id == chatbot_id, Conversation.created_at >= cutoff
    ))).scalar_one()
    resolved = (await db.execute(select(func.count(Conversation.id)).where(
        Conversation.chatbot_id == chatbot_id, Conversation.created_at >= cutoff, Conversation.autonomous_resolved == True
    ))).scalar_one()
    escalated = (await db.execute(select(func.count(Conversation.id)).where(
        Conversation.chatbot_id == chatbot_id, Conversation.created_at >= cutoff, Conversation.outcome == "escalated_to_human"
    ))).scalar_one()

    # Sentiment
    avg_sentiment = (await db.execute(select(func.avg(ConversationAnalysis.sentiment_score)).where(
        ConversationAnalysis.workspace_id == workspace.id,
        ConversationAnalysis.sentiment_score.isnot(None),
    ).where(ConversationAnalysis.conversation_id.in_(
        select(Conversation.id).where(Conversation.chatbot_id == chatbot_id, Conversation.created_at >= cutoff)
    )))).scalar_one()
    avg_sentiment = round(float(avg_sentiment), 2) if avg_sentiment else None

    # Feedback
    feedback_filter = select(MessageFeedback.id).join(
        Conversation, Conversation.id == MessageFeedback.conversation_id
    ).where(Conversation.chatbot_id == chatbot_id, MessageFeedback.created_at >= cutoff)
    thumbs_up = (await db.execute(select(func.count()).select_from(feedback_filter.where(MessageFeedback.rating == "thumbs_up").subquery()))).scalar_one()
    thumbs_down = (await db.execute(select(func.count()).select_from(feedback_filter.where(MessageFeedback.rating == "thumbs_down").subquery()))).scalar_one()

    # Topics
    topics_result = await db.execute(
        select(func.unnest(ConversationAnalysis.topics).label("topic"))
        .where(ConversationAnalysis.workspace_id == workspace.id)
        .where(ConversationAnalysis.conversation_id.in_(
            select(Conversation.id).where(Conversation.chatbot_id == chatbot_id)
        ))
    )
    topic_counts = {}
    for (topic,) in topics_result.all():
        if topic:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:8]

    # Derived
    unresolved = total - resolved - escalated
    resolution_rate = round(resolved / total * 100) if total > 0 else 0
    positive_pct = round(thumbs_up / (thumbs_up + thumbs_down) * 100) if (thumbs_up + thumbs_down) > 0 else None

    # Gaps
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot_id))
    kbs = kb_result.scalars().all()
    gaps = (await db.execute(
        select(GapCluster).where(GapCluster.workspace_id == workspace.id, GapCluster.chatbot_id == chatbot_id, GapCluster.status == "open")
        .order_by(GapCluster.gap_count.desc()).limit(5)
    )).scalars().all()

    # Recent conversations
    recent = (await db.execute(
        select(Conversation).where(Conversation.chatbot_id == chatbot_id)
        .order_by(Conversation.created_at.desc()).limit(5)
    )).scalars().all()

    # Doc count
    doc_count = 0
    if kbs:
        doc_count = (await db.execute(
            select(func.count(Document.id)).where(Document.knowledge_base_id.in_([kb.id for kb in kbs]))
        )).scalar_one()

    # Actions
    from app.models.actions import ChatbotAction
    actions = (await db.execute(
        select(ChatbotAction).where(ChatbotAction.chatbot_id == chatbot_id).order_by(ChatbotAction.created_at)
    )).scalars().all()

    return request.app.state.templates.TemplateResponse("chatbots/detail.html", {
        "request": request, "chatbot": chatbot, "days": days,
        "total": total, "resolved": resolved, "escalated": escalated, "unresolved": unresolved,
        "resolution_rate": resolution_rate,
        "avg_sentiment": avg_sentiment, "thumbs_up": thumbs_up, "thumbs_down": thumbs_down,
        "positive_pct": positive_pct,
        "top_topics": top_topics, "gaps": gaps, "recent": recent,
        "knowledge_bases": kbs, "doc_count": doc_count, "actions": actions,
        "now": now,
    })


@router.put("/chatbots/{chatbot_id}")
async def update_chatbot(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    form = await request.form()
    for key in ("name", "system_prompt", "tone", "language", "welcome_message", "fallback_message", "display_name", "llm_model"):
        if key in form:
            setattr(chatbot, key, form[key])
    # JSON array field
    if "suggested_questions" in form:
        import json as _json
        try:
            chatbot.suggested_questions = _json.loads(form["suggested_questions"])
        except (ValueError, TypeError):
            pass
    # Float fields
    for key in ("temperature", "confidence_threshold"):
        if key in form:
            try:
                setattr(chatbot, key, float(form[key]))
            except (ValueError, TypeError):
                pass
    # Int fields
    if "retrieval_top_k" in form:
        try:
            setattr(chatbot, "retrieval_top_k", int(form["retrieval_top_k"]))
        except (ValueError, TypeError):
            pass
    # Checkbox fields (present with value "true" when checked, absent when unchecked)
    chatbot.use_reranking = form.get("use_reranking") == "true"
    chatbot.use_hybrid_retrieval = form.get("use_hybrid_retrieval") == "true"
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Chatbot updated", "type": "success",
        })
    return RedirectResponse(f"/chatbots/{chatbot_id}", status_code=303)


@router.delete("/chatbots/{chatbot_id}")
async def delete_chatbot(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    await db.delete(chatbot)
    await db.flush()
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # HTMX removes the row
    return RedirectResponse("/chatbots", status_code=303)


@router.post("/chatbots/{chatbot_id}/toggle")
async def toggle_chatbot(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if chatbot:
        chatbot.is_active = not chatbot.is_active
        await db.flush()
    return HTMLResponse("")


@router.get("/chatbots/{chatbot_id}/sources", response_class=HTMLResponse)
async def chatbot_sources(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot_id))
    kbs = kb_result.scalars().all()
    docs = []
    failed_docs = []
    if kbs:
        kb_ids = [kb.id for kb in kbs]
        doc_result = await db.execute(
            select(Document).where(Document.knowledge_base_id.in_(kb_ids))
            .order_by(Document.created_at.desc())
        )
        docs = doc_result.scalars().all()
        failed_docs = [d for d in docs if d.status == "failed"]

    # Character usage
    from app.services.plan_service import get_plan_limits
    limits = get_plan_limits(workspace.plan or "free")
    char_limit = limits.get("chars_indexed", -1)
    char_usage = {
        "used": workspace.chars_indexed,
        "limit": char_limit if char_limit > 0 else None,
    }

    # Crawl history
    from app.models.knowledge import CrawlJob
    crawl_jobs = []
    if kbs:
        crawl_result = await db.execute(
            select(CrawlJob).where(CrawlJob.kb_id.in_([kb.id for kb in kbs]))
            .order_by(CrawlJob.created_at.desc())
        )
        crawl_jobs = crawl_result.scalars().all()

    return request.app.state.templates.TemplateResponse("chatbots/sources.html", {
        "request": request, "chatbot": chatbot, "documents": docs, "knowledge_bases": kbs,
        "char_usage": char_usage, "failed_docs": failed_docs, "crawl_jobs": crawl_jobs,
    })


@router.get("/chatbots/{chatbot_id}/deploy", response_class=HTMLResponse)
async def chatbot_deploy(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    return request.app.state.templates.TemplateResponse("chatbots/deploy.html", {
        "request": request, "chatbot": chatbot, "base_url": settings.BASE_URL,
    })


@router.get("/chatbots/{chatbot_id}/chat", response_class=HTMLResponse)
async def chatbot_test_chat(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    return request.app.state.templates.TemplateResponse("chatbots/chat.html", {
        "request": request, "chatbot": chatbot,
    })


@router.get("/chatbots/{chatbot_id}/customize", response_class=HTMLResponse)
async def chatbot_customize(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    return request.app.state.templates.TemplateResponse("chatbots/customize.html", {
        "request": request, "chatbot": chatbot,
    })


@router.post("/chatbots/{chatbot_id}/customize")
async def update_customize(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    form = await request.form()
    wc = dict(chatbot.widget_config or {})
    for key in ("primary_color", "text_color", "position", "initial_open", "window_title", "input_placeholder", "custom_css"):
        if key in form:
            wc[key] = form[key] or None
    wc["show_branding"] = form.get("show_branding") == "true"
    wc["lead_capture_enabled"] = form.get("lead_capture_enabled") == "true"
    wc["persist_conversation"] = form.get("persist_conversation") == "true"
    raw_domains = form.get("allowed_domains", "")
    wc["allowed_domains"] = [d.strip() for d in raw_domains.splitlines() if d.strip()]
    # Lead capture fields (multi-value)
    lead_fields = form.getlist("lead_capture_fields")
    if lead_fields:
        wc["lead_capture_fields"] = lead_fields
    # Auto open delay
    if "auto_open_delay" in form and form["auto_open_delay"]:
        try:
            wc["auto_open_delay"] = int(form["auto_open_delay"])
        except (ValueError, TypeError):
            wc["auto_open_delay"] = None
    else:
        wc["auto_open_delay"] = None
    # Quick replies (JSON array)
    import json as _json
    if "quick_replies" in form:
        try:
            wc["quick_replies"] = _json.loads(form["quick_replies"])
        except (ValueError, TypeError):
            pass
    chatbot.widget_config = wc
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(chatbot, "widget_config")
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Appearance saved", "type": "success",
        })
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/chatbots/{chatbot_id}/customize", status_code=303)


@router.get("/chatbots/{chatbot_id}/settings", response_class=HTMLResponse)
async def chatbot_settings(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    return request.app.state.templates.TemplateResponse("chatbots/settings.html", {
        "request": request, "chatbot": chatbot,
    })
