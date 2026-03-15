"""Add HNSW index on chunks.embedding for pgvector cosine similarity

Revision ID: ff9944a786c6
Revises: 2026_03_13_document_content_hash
Create Date: 2026-03-13
"""
from alembic import op

# revision identifiers
revision = "ff9944a786c6"
down_revision = "2026_03_13_document_content_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # HNSW index requires CREATE INDEX CONCURRENTLY which cannot run inside a transaction.
    # End the implicit transaction that Alembic opens.
    op.execute("COMMIT")
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_hnsw")
