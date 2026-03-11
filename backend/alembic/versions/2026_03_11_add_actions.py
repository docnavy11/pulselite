"""add_actions

Revision ID: add_actions
Revises: add_crawl_and_autoconfig
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "add_actions"
down_revision = "add_crawl_and_autoconfig"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chatbot_actions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("chatbot_id", UUID(as_uuid=True), sa.ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
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
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chatbot_id", UUID(as_uuid=True), sa.ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action_id", UUID(as_uuid=True), sa.ForeignKey("chatbot_actions.id", ondelete="CASCADE"), nullable=False),
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
