"""Add character budget columns and path filters for crawl

Revision ID: crawl_char_limits
Revises: add_action_parameters
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "crawl_char_limits"
down_revision = "add_action_parameters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # workspaces: total chars currently indexed across all KBs
    op.add_column(
        "workspaces",
        sa.Column(
            "chars_indexed",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # documents: char count of extractor output for this document
    op.add_column(
        "documents",
        sa.Column(
            "char_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # crawl_jobs: drop page-cap columns
    op.drop_column("crawl_jobs", "max_pages")
    op.drop_column("crawl_jobs", "over_limit")

    # crawl_jobs: add path filter columns
    op.add_column(
        "crawl_jobs",
        sa.Column(
            "include_paths",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "crawl_jobs",
        sa.Column(
            "exclude_paths",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # Backfill char_count for existing indexed documents using their chunk text.
    # Chunks do not overlap, so SUM(length) approximates extractor output length.
    # NOTE: This is a bulk UPDATE. On a large production DB this will lock the
    # documents table briefly. Run during a maintenance window or accept the
    # brief lock on the first deployment.
    op.execute("""
        UPDATE documents d
        SET    char_count = sub.total
        FROM   (
            SELECT document_id, COALESCE(SUM(LENGTH(content)), 0) AS total
            FROM   chunks
            GROUP BY document_id
        ) sub
        WHERE  d.id = sub.document_id
          AND  d.status = 'indexed'
    """)

    # Backfill chars_indexed on workspaces
    op.execute("""
        UPDATE workspaces w
        SET    chars_indexed = sub.total
        FROM   (
            SELECT workspace_id, COALESCE(SUM(char_count), 0) AS total
            FROM   documents
            WHERE  status = 'indexed'
            GROUP BY workspace_id
        ) sub
        WHERE  w.id = sub.workspace_id
    """)


def downgrade() -> None:
    op.drop_column("crawl_jobs", "exclude_paths")
    op.drop_column("crawl_jobs", "include_paths")
    op.add_column(
        "crawl_jobs",
        sa.Column("over_limit", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.add_column(
        "crawl_jobs",
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default=sa.text("50")),
    )
    op.drop_column("documents", "char_count")
    op.drop_column("workspaces", "chars_indexed")
