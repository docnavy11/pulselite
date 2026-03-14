"""add workspace last_report_sent_at

Revision ID: a3f7c1d9e24b
Revises: ba95cbd3f658
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c1d9e24b'
down_revision: Union[str, None] = 'ba95cbd3f658'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workspaces', sa.Column('last_report_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('workspaces', 'last_report_sent_at')
