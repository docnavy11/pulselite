"""merge heads before feedback

Revision ID: merge_heads_feedback
Revises: 2bc7ef1897a4, 737f5dc93f17
Create Date: 2026-03-08 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'merge_heads_feedback'
down_revision: Union[str, tuple, None] = ('2bc7ef1897a4', '737f5dc93f17')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
