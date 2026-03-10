"""add message feedback

Revision ID: add_message_feedback
Revises: merge_heads_feedback
Create Date: 2026-03-08 12:01:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'add_message_feedback'
down_revision: Union[str, None] = 'merge_heads_feedback'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'message_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rating', sa.String(10), nullable=False),  # 'thumbs_up' or 'thumbs_down'
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_message_feedback_message_id', 'message_feedback', ['message_id'])
    op.create_index('ix_message_feedback_workspace_id', 'message_feedback', ['workspace_id'])

def downgrade() -> None:
    op.drop_index('ix_message_feedback_workspace_id', table_name='message_feedback')
    op.drop_index('ix_message_feedback_message_id', table_name='message_feedback')
    op.drop_table('message_feedback')
