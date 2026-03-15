"""Add content_hash column to documents."""
import sqlalchemy as sa
from alembic import op

revision = "2026_03_13_document_content_hash"
down_revision = "2026_03_13_chatbot_archived_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "content_hash")
