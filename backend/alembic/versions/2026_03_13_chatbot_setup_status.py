"""Add setup_status and active_crawl_job_id to chatbots

Revision ID: 2026_03_13_chatbot_setup_status
Revises: 2026_03_12_doc_ingest_log
Create Date: 2026-03-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_03_13_chatbot_setup_status"
down_revision = "2026_03_12_doc_ingest_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chatbots", sa.Column("setup_status", sa.Text(), nullable=True))
    op.alter_column("chatbots", "setup_status", type_=sa.Text())
    op.add_column(
        "chatbots",
        sa.Column(
            "active_crawl_job_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_chatbots_active_crawl_job",
        "chatbots",
        "crawl_jobs",
        ["active_crawl_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chatbots_active_crawl_job", "chatbots", type_="foreignkey")
    op.drop_column("chatbots", "active_crawl_job_id")
    op.drop_column("chatbots", "setup_status")
