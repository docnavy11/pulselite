"""add crawl_jobs table and chatbot autoconfig fields

Revision ID: add_crawl_and_autoconfig
Revises: drop_enterprise_features
Create Date: 2026-03-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "add_crawl_and_autoconfig"
down_revision = "drop_enterprise_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("root_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("pages_discovered", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pages_queued", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pages_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("over_limit", sa.Boolean(), server_default="FALSE", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("chatbots", sa.Column("brand_color", sa.String(7), nullable=True))
    op.add_column("chatbots", sa.Column("welcome_message", sa.Text(), nullable=True))
    op.add_column("chatbots", sa.Column("suggested_questions", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("chatbots", "suggested_questions")
    op.drop_column("chatbots", "welcome_message")
    op.drop_column("chatbots", "brand_color")
    op.drop_table("crawl_jobs")
