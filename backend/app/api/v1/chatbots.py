import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.knowledge import Chatbot as ChatbotModel
from app.models.organizational import Agent
from app.schemas.chatbots import ChatbotCreate, ChatbotResponse, ChatbotUpdate
from app.schemas.widget import LLMConfigUpdate, PersonaUpdate, WidgetConfig
from app.services import chatbot_service
from app.services.audit import log_audit
from app.services.encryption import encrypt_api_key

router = APIRouter(prefix="/workspaces/{workspace_id}/chatbots", tags=["chatbots"])


@router.post("", response_model=ChatbotResponse)
async def create_chatbot(
    request: Request,
    body: ChatbotCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chatbot = await chatbot_service.create_chatbot(db, workspace_id, **body.model_dump())
    await log_audit(
        db,
        workspace_id,
        "chatbot.create",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="chatbot",
        resource_id=str(chatbot.id),
        resource_name=chatbot.name,
        ip_address=request.client.host if request.client else None,
    )
    return chatbot


@router.get("", response_model=list[ChatbotResponse])
async def list_chatbots(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await chatbot_service.list_chatbots(db, workspace_id)


@router.get("/{chatbot_id}", response_model=ChatbotResponse)
async def get_chatbot(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await chatbot_service.get_chatbot(db, workspace_id, chatbot_id)


@router.put("/{chatbot_id}", response_model=ChatbotResponse)
async def update_chatbot(
    request: Request,
    chatbot_id: uuid.UUID,
    body: ChatbotUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chatbot = await chatbot_service.update_chatbot(db, workspace_id, chatbot_id, **body.model_dump(exclude_unset=True))
    await log_audit(
        db,
        workspace_id,
        "chatbot.update",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="chatbot",
        resource_id=str(chatbot_id),
        resource_name=chatbot.name,
        ip_address=request.client.host if request.client else None,
    )
    return chatbot


@router.delete("/{chatbot_id}", status_code=204)
async def delete_chatbot(
    request: Request,
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch name before deleting for the audit record
    result = await db.execute(
        select(ChatbotModel).where(
            ChatbotModel.id == chatbot_id,
            ChatbotModel.workspace_id == workspace_id,
        )
    )
    existing = result.scalar_one_or_none()
    chatbot_name = existing.name if existing else str(chatbot_id)
    await chatbot_service.delete_chatbot(db, workspace_id, chatbot_id)
    await log_audit(
        db,
        workspace_id,
        "chatbot.delete",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="chatbot",
        resource_id=str(chatbot_id),
        resource_name=chatbot_name,
        ip_address=request.client.host if request.client else None,
    )


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
    request: Request,
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
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
    await log_audit(
        db,
        workspace_id,
        "chatbot.duplicate",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="chatbot",
        resource_id=str(new_chatbot.id),
        resource_name=new_chatbot.name,
        ip_address=request.client.host if request.client else None,
        metadata={"source_chatbot_id": str(chatbot_id)},
    )
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
