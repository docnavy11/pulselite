"""add country columns to conversations

Revision ID: add_conversation_country
Revises: add_white_label
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "add_conversation_country"
down_revision = "add_white_label"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("country_code", sa.String(2), nullable=True))
    op.add_column("conversations", sa.Column("country_name", sa.String(100), nullable=True))
    op.create_index(
        "ix_conversations_country_code",
        "conversations",
        ["country_code"],
    )


def downgrade():
    op.drop_index("ix_conversations_country_code", table_name="conversations")
    op.drop_column("conversations", "country_name")
    op.drop_column("conversations", "country_code")
