"""add 2FA columns to agents

Revision ID: add_2fa
Revises: add_conversation_country
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "add_2fa"
down_revision = "add_conversation_country"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agents", sa.Column("totp_secret", sa.String(255), nullable=True))
    op.add_column(
        "agents",
        sa.Column(
            "two_fa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade():
    op.drop_column("agents", "two_fa_enabled")
    op.drop_column("agents", "totp_secret")
