import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import Chatbot
from app.schemas.widget import WidgetConfig

router = APIRouter(tags=["share"])


class ShareResponse(BaseModel):
    chatbot_id: str
    name: str
    display_name: str
    avatar_url: str | None
    tone: str
    widget_config: WidgetConfig


@router.get("/share/{chatbot_id}", response_model=ShareResponse)
async def get_share_config(chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.is_active == True))  # noqa: E712
    chatbot = result.scalar_one_or_none()
    if chatbot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chatbot not found")

    widget_cfg = chatbot.widget_config or {}
    return ShareResponse(
        chatbot_id=str(chatbot.id),
        name=chatbot.name,
        display_name=chatbot.display_name,
        avatar_url=chatbot.avatar_url,
        tone=chatbot.tone,
        widget_config=WidgetConfig(**widget_cfg) if widget_cfg else WidgetConfig(),
    )
