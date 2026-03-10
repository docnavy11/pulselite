"""add workspace webhooks

Revision ID: add_workspace_webhooks
Revises: add_message_feedback
Create Date: 2026-03-08 13:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'add_workspace_webhooks'
down_revision: Union[str, None] = 'add_message_feedback'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workspace_webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('event_types', postgresql.JSONB(), server_default=sa.text("'[\"conversation.created\", \"conversation.escalated\"]'::jsonb"), nullable=False),
        sa.Column('secret', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_workspace_webhooks_workspace_id', 'workspace_webhooks', ['workspace_id'])


def downgrade() -> None:
    op.drop_index('ix_workspace_webhooks_workspace_id', table_name='workspace_webhooks')
    op.drop_table('workspace_webhooks')
