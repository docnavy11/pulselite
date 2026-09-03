"""Add HNSW index on chunks.embedding for pgvector cosine similarity

Revision ID: ff9944a786c6
Revises: 2026_03_13_document_content_hash
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "ff9944a786c6"
down_revision = "2026_03_13_document_content_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # WARNING — PRODUCTION DEPLOYMENT WITH LARGE TABLES
    # =========================================================================
    # This migration uses non-concurrent index creation because Alembic runs
    # inside a transaction, and CREATE INDEX CONCURRENTLY cannot run within a
    # transaction block.
    #
    # For large production tables (>100k rows), non-concurrent index creation
    # will LOCK THE TABLE for the duration of the build, potentially causing
    # downtime. In that case, skip this migration and create the index manually:
    #
    #   CREATE INDEX CONCURRENTLY idx_chunks_embedding_hnsw
    #   ON chunks USING hnsw (embedding vector_cosine_ops)
    #   WITH (m = 16, ef_construction = 64);
    #
    # Then mark this migration as applied: alembic stamp ff9944a786c6
    # =========================================================================
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_hnsw")
