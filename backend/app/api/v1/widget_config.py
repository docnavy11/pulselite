import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import Chatbot
from app.schemas.widget import WidgetConfig, WidgetConfigResponse

router = APIRouter(tags=["widget"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/widget/{chatbot_id}/config", response_model=WidgetConfigResponse)
@limiter.limit("60/minute")
async def get_widget_config(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.is_active == True))  # noqa: E712
    chatbot = result.scalar_one_or_none()
    if chatbot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chatbot not found")

    widget_cfg = chatbot.widget_config or {}
    parsed_cfg = WidgetConfig(**widget_cfg) if widget_cfg else WidgetConfig()
    return WidgetConfigResponse(
        chatbot_id=str(chatbot.id),
        workspace_id=str(chatbot.workspace_id),
        display_name=chatbot.display_name,
        avatar_url=chatbot.avatar_url or parsed_cfg.avatar_url,
        widget_config=parsed_cfg,
        primary_color=parsed_cfg.primary_color,
        position=parsed_cfg.position,
        welcome_message=parsed_cfg.welcome_message,
        launcher_text=parsed_cfg.launcher_text,
        quick_replies=parsed_cfg.quick_replies,
        lead_capture_enabled=parsed_cfg.lead_capture_enabled,
        lead_capture_fields=parsed_cfg.lead_capture_fields,
        gdpr_consent_enabled=parsed_cfg.gdpr_consent_enabled,
        gdpr_consent_text=parsed_cfg.gdpr_consent_text,
        allowed_domains=parsed_cfg.allowed_domains,
        auto_open_delay=parsed_cfg.auto_open_delay,
        persist_conversation=parsed_cfg.persist_conversation,
        custom_css=parsed_cfg.custom_css,
    )
