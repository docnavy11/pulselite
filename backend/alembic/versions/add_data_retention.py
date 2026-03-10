"""add data_retention_days to workspaces

Revision ID: add_data_retention
Revises: add_sso_configs
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "add_data_retention"
down_revision = "add_sso_configs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workspaces",
        sa.Column("data_retention_days", sa.Integer, nullable=True),
    )


def downgrade():
    op.drop_column("workspaces", "data_retention_days")
