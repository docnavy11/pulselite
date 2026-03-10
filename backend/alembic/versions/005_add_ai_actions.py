"""add_ai_actions

Revision ID: 005
Revises: 737f5dc93f17
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "737f5dc93f17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chatbot_actions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("chatbot_id", UUID(as_uuid=True), sa.ForeignKey("chatbots.id"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("trigger_description", sa.Text(), nullable=False),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "action_events",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("chatbot_id", UUID(as_uuid=True), sa.ForeignKey("chatbots.id"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("action_id", UUID(as_uuid=True), sa.ForeignKey("chatbot_actions.id"), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'fired'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_index("idx_chatbot_actions_chatbot", "chatbot_actions", ["chatbot_id"])
    op.create_index("idx_chatbot_actions_workspace", "chatbot_actions", ["workspace_id"])
    op.create_index("idx_action_events_workspace", "action_events", ["workspace_id"])
    op.create_index("idx_action_events_chatbot", "action_events", ["chatbot_id"])
    op.create_index("idx_action_events_conversation", "action_events", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("idx_action_events_conversation", "action_events")
    op.drop_index("idx_action_events_chatbot", "action_events")
    op.drop_index("idx_action_events_workspace", "action_events")
    op.drop_index("idx_chatbot_actions_workspace", "chatbot_actions")
    op.drop_index("idx_chatbot_actions_chatbot", "chatbot_actions")
    op.drop_table("action_events")
    op.drop_table("chatbot_actions")
