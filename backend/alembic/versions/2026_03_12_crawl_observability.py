"""Add phase and error_message to crawl_jobs

Revision ID: 2026_03_12_crawl_observability
Revises: 2026_03_12_crawl_char_limits
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_12_crawl_observability"
down_revision = "crawl_char_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crawl_jobs", sa.Column("phase", sa.Text(), nullable=True))
    op.add_column("crawl_jobs", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("crawl_jobs", "error_message")
    op.drop_column("crawl_jobs", "phase")
