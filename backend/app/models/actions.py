import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatbotAction(Base):
    __tablename__ = "chatbot_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"), primary_key=True)
    chatbot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_description: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)


class ActionEvent(Base):
    __tablename__ = "action_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    chatbot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    action_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbot_actions.id", ondelete="CASCADE"), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'fired'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
