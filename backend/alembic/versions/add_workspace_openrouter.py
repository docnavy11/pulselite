# backend/alembic/versions/add_workspace_openrouter.py
"""add openrouter columns to workspaces

Revision ID: add_workspace_openrouter
Revises: add_2fa
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "add_workspace_openrouter"
down_revision = "add_2fa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workspaces",
        sa.Column("openrouter_api_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "allowed_models",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade():
    op.drop_column("workspaces", "allowed_models")
    op.drop_column("workspaces", "openrouter_api_key")
