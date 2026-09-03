import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.conversations import Conversation
from app.models.knowledge import Chatbot as ChatbotModel, CrawlJob
from app.models.organizational import Agent, Workspace
from app.schemas.chatbots import AutoConfigRequest, AutoConfigResponse, ChatbotCreate, ChatbotResponse, ChatbotUpdate, CrawlProgressResponse
from app.schemas.widget import LLMConfigUpdate, PersonaUpdate, WidgetConfig
from app.config import settings as app_settings
from app.services import chatbot_service
from app.services.audit_service import record_audit_event
from app.services.encryption import encrypt_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}/chatbots", tags=["chatbots"])


@router.post("", response_model=ChatbotResponse)
async def create_chatbot(
    body: ChatbotCreate,
    request: Request,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = ws_result.scalar_one()

    # Validate that AI is configured (workspace key or env-level key)
    has_ai_key = bool(ws.openrouter_api_key or app_settings.AI_API_KEY)
    if not has_ai_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No AI provider configured. Set AI_API_KEY in your .env file or add an API key in Settings > AI Models.",
        )

    data = body.model_dump()
    # Apply workspace default chatbot model if the request uses the schema default
    if body.llm_model == "claude-haiku-4-5-20251001":
        default = ws.default_chatbot_model or app_settings.DEFAULT_CHATBOT_MODEL
        if default:
            data["llm_model"] = default

    # Validate model is in allowed_models (if workspace has a restricted list)
    if ws.allowed_models and data.get("llm_model") and data["llm_model"] not in ws.allowed_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{data['llm_model']}' is not in the workspace's allowed models list.",
        )

    chatbot = await chatbot_service.create_chatbot(db, workspace_id, **data)

    await record_audit_event(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        user_email=current_user.email,
        action="chatbot.created",
        resource_type="chatbot",
        resource_id=chatbot.id,
        ip_address=request.client.host if request.client else None,
        details={"name": chatbot.name},
    )

    return chatbot


@router.get("", response_model=list[ChatbotResponse])
async def list_chatbots(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    include_archived: bool = Query(False),
):
    chatbots = await chatbot_service.list_chatbots(db, workspace_id, include_archived=include_archived)

    # Batch-fetch CrawlJob data for bots with active_crawl_job_id (no N+1)
    crawl_job_ids = [c.active_crawl_job_id for c in chatbots if c.active_crawl_job_id]
    crawl_jobs: dict[uuid.UUID, CrawlJob] = {}
    if crawl_job_ids:
        result = await db.execute(select(CrawlJob).where(CrawlJob.id.in_(crawl_job_ids)))
        for job in result.scalars():
            crawl_jobs[job.id] = job

    responses = []
    for c in chatbots:
        r = ChatbotResponse.model_validate(c)
        if c.active_crawl_job_id and c.active_crawl_job_id in crawl_jobs:
            job = crawl_jobs[c.active_crawl_job_id]
            r = r.model_copy(update={
                "crawl_progress": CrawlProgressResponse(
                    pages_queued=job.pages_queued,
                    pages_discovered=job.pages_discovered,
                    status=job.status,
                    error_message=job.error_message,
                )
            })
        responses.append(r)
    return responses


@router.get("/stats/summary")
async def get_chatbot_stats(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Return per-chatbot stats: conversations (30d), resolution rate (30d), last active."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    rows = await db.execute(
        select(
            Conversation.chatbot_id,
            func.count().label("total"),
            func.count().filter(Conversation.autonomous_resolved == True).label("resolved"),  # noqa: E712
            func.max(Conversation.created_at).label("last_active"),
        )
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= cutoff,
            Conversation.chatbot_id.isnot(None),
        )
        .group_by(Conversation.chatbot_id)
    )
    result = {}
    for row in rows.all():
        result[str(row.chatbot_id)] = {
            "conversations_30d": row.total,
            "resolution_rate": round(row.resolved / row.total, 3) if row.total else 0.0,
            "last_active": row.last_active.isoformat() if row.last_active else None,
        }
    return result


@router.get("/{chatbot_id}", response_model=ChatbotResponse)
async def get_chatbot(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    chatbot = await chatbot_service.get_chatbot(db, workspace_id, chatbot_id)
    r = ChatbotResponse.model_validate(chatbot)
    if chatbot.active_crawl_job_id:
        job_result = await db.execute(select(CrawlJob).where(CrawlJob.id == chatbot.active_crawl_job_id))
        job = job_result.scalar_one_or_none()
        if job:
            r = r.model_copy(update={
                "crawl_progress": CrawlProgressResponse(
                    pages_queued=job.pages_queued,
                    pages_discovered=job.pages_discovered,
                    status=job.status,
                    error_message=job.error_message,
                )
            })
    return r


@router.put("/{chatbot_id}", response_model=ChatbotResponse)
async def update_chatbot(
    chatbot_id: uuid.UUID,
    body: ChatbotUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    chatbot = await chatbot_service.update_chatbot(db, workspace_id, chatbot_id, **body.model_dump(exclude_unset=True))
    return chatbot


@router.delete("/{chatbot_id}", status_code=204)
async def delete_chatbot(
    chatbot_id: uuid.UUID,
    request: Request,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await chatbot_service.delete_chatbot(db, workspace_id, chatbot_id)

    await record_audit_event(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        user_email=current_user.email,
        action="chatbot.deleted",
        resource_type="chatbot",
        resource_id=chatbot_id,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/{chatbot_id}/archive", response_model=ChatbotResponse)
async def archive_chatbot(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    chatbot = await chatbot_service.archive_chatbot(db, workspace_id, chatbot_id)
    return chatbot


@router.post("/{chatbot_id}/unarchive", response_model=ChatbotResponse)
async def unarchive_chatbot(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    chatbot = await chatbot_service.unarchive_chatbot(db, workspace_id, chatbot_id)
    return chatbot


@router.get("/{chatbot_id}/widget-config", response_model=WidgetConfig)
async def get_widget_config(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatbotModel).where(
            ChatbotModel.id == chatbot_id,
            ChatbotModel.workspace_id == workspace_id,
        )
    )
    chatbot = result.scalar_one_or_none()
    if chatbot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chatbot not found")
    widget_cfg = chatbot.widget_config or {}
    return WidgetConfig(**widget_cfg) if widget_cfg else WidgetConfig()


@router.put("/{chatbot_id}/widget-config", response_model=ChatbotResponse)
async def update_widget_config(
    chatbot_id: uuid.UUID,
    body: WidgetConfig,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await chatbot_service.update_chatbot(db, workspace_id, chatbot_id, widget_config=body.model_dump())


@router.put("/{chatbot_id}/persona", response_model=ChatbotResponse)
async def update_persona(
    chatbot_id: uuid.UUID,
    body: PersonaUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await chatbot_service.update_chatbot(db, workspace_id, chatbot_id, **body.model_dump(exclude_unset=True))


@router.post("/{chatbot_id}/duplicate", response_model=ChatbotResponse)
async def duplicate_chatbot(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    source = await chatbot_service.get_chatbot(db, workspace_id, chatbot_id)
    new_chatbot = ChatbotModel(
        workspace_id=source.workspace_id,
        name=f"{source.name} (copy)",
        display_name=f"{source.display_name} (copy)",
        system_prompt=source.system_prompt,
        tone=source.tone,
        language=source.language,
        llm_provider=source.llm_provider,
        llm_model=source.llm_model,
        temperature=source.temperature,
        max_tokens=source.max_tokens,
        confidence_threshold=source.confidence_threshold,
        retrieval_top_k=source.retrieval_top_k,
        use_reranking=source.use_reranking,
        use_hybrid_retrieval=source.use_hybrid_retrieval,
        widget_config=source.widget_config,
        fallback_type=source.fallback_type,
        fallback_message=source.fallback_message,
    )
    db.add(new_chatbot)
    await db.commit()
    await db.refresh(new_chatbot)
    return new_chatbot


@router.put("/{chatbot_id}/llm-config", response_model=ChatbotResponse)
async def update_llm_config(
    chatbot_id: uuid.UUID,
    body: LLMConfigUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)
    if "byoak" in update_data and update_data["byoak"]:
        update_data["byoak"] = encrypt_api_key(update_data["byoak"])
    return await chatbot_service.update_chatbot(db, workspace_id, chatbot_id, **update_data)


@router.post("/{chatbot_id}/autoconfig", response_model=AutoConfigResponse)
async def run_autoconfig(
    chatbot_id: uuid.UUID,
    body: AutoConfigRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    from app.services import autoconfig_service

    try:
        chatbot = await autoconfig_service.run(db, chatbot_id, body.knowledge_base_id, workspace_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
    except RuntimeError as e:
        logger.error("AI configuration failed for chatbot: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI configuration failed. Please try again.",
        )
    except Exception as e:
        logger.error("Unexpected error during chatbot configuration: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error during configuration. Please try again.",
        )

    return AutoConfigResponse(
        name=chatbot.name,
        welcome_message=chatbot.welcome_message,
        system_prompt=chatbot.system_prompt,
        suggested_questions=chatbot.suggested_questions,
        fallback_message=chatbot.fallback_message,
        brand_color=chatbot.brand_color,
        tone=chatbot.tone,
        language=chatbot.language,
    )
