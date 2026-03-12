"""Add error_message and ingestion_steps to documents

Revision ID: 2026_03_12_doc_ingest_log
Revises: 2026_03_12_crawl_observability
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_03_12_doc_ingest_log"
down_revision = "2026_03_12_crawl_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("ingestion_steps", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "ingestion_steps")
    op.drop_column("documents", "error_message")
