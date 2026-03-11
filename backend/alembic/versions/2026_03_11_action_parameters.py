"""add action parameters

Revision ID: add_action_parameters
Revises: add_actions
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "add_action_parameters"
down_revision = "add_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chatbot_actions",
        sa.Column("parameters", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("chatbot_actions", "parameters")
