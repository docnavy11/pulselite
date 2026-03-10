"""add white_label_enabled to workspaces

Revision ID: add_white_label
Revises: add_audit_logs
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "add_white_label"
down_revision = "add_audit_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workspaces",
        sa.Column(
            "white_label_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade():
    op.drop_column("workspaces", "white_label_enabled")
