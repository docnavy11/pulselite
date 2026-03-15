"""change embedding vector 1536 to 384

Revision ID: 9187fe5ac70d
Revises: c568c7ff8d42
Create Date: 2026-03-14 07:58:49.354007

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9187fe5ac70d'
down_revision: Union[str, None] = 'c568c7ff8d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clear existing embeddings (they're 1536-dim, incompatible with new 384-dim)
    op.execute("UPDATE chunks SET embedding = NULL")
    # Change the vector column dimension
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(384)")


def downgrade() -> None:
    op.execute("UPDATE chunks SET embedding = NULL")
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1536)")
