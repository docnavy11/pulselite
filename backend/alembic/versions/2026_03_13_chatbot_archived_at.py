"""Add archived_at to chatbots

Revision ID: 2026_03_13_chatbot_archived_at
Revises: 2026_03_13_chatbot_setup_status
Create Date: 2026-03-13
"""
import sqlalchemy as sa
from alembic import op

revision = "2026_03_13_chatbot_archived_at"
down_revision = "2026_03_13_chatbot_setup_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chatbots",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chatbots", "archived_at")
