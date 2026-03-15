"""Add indexes on documents and crawl_jobs for query performance

Revision ID: 610382505390
Revises: ff9944a786c6
Create Date: 2026-03-13
"""
from alembic import op

# revision identifiers
revision = "610382505390"
down_revision = "ff9944a786c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_documents_kb_status",
        "documents",
        ["knowledge_base_id", "status"],
    )
    op.create_index(
        "idx_crawl_jobs_kb_id",
        "crawl_jobs",
        ["kb_id"],
    )
    op.create_index(
        "idx_documents_content_hash",
        "documents",
        ["content_hash"],
        postgresql_where="content_hash IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("idx_documents_content_hash", table_name="documents")
    op.drop_index("idx_crawl_jobs_kb_id", table_name="crawl_jobs")
    op.drop_index("idx_documents_kb_status", table_name="documents")
