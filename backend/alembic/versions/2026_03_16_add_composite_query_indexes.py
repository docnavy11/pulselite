"""Add composite indexes for common query patterns

These indexes support the most frequent dashboard queries:
- Conversations listed by workspace + created_at (paginated feeds)
- Conversations filtered by chatbot + status + created_at (filtered views)
- Conversation analysis by workspace + created_at (sentiment/analytics)
- Gap clusters by workspace + status (knowledge gaps dashboard)

Revision ID: 96fa9b13008a
Revises: 2026_03_16_audit
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "96fa9b13008a"
down_revision: Union[str, None] = "2026_03_16_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_conversations_workspace_created",
        "conversations",
        ["workspace_id", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_conversations_chatbot_status_created",
        "conversations",
        ["chatbot_id", "status", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_conversation_analysis_workspace_created",
        "conversation_analysis",
        ["workspace_id", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_gap_clusters_workspace_status",
        "gap_clusters",
        ["workspace_id", "status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_documents_workspace_kb",
        "documents",
        ["workspace_id", "knowledge_base_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_audit_logs_workspace_timestamp",
        "audit_logs",
        ["workspace_id", "timestamp"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_gap_events_workspace_created",
        "gap_events",
        ["workspace_id", "created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_gap_events_workspace_created", table_name="gap_events")
    op.drop_index("ix_audit_logs_workspace_timestamp", table_name="audit_logs")
    op.drop_index("ix_documents_workspace_kb", table_name="documents")
    op.drop_index("ix_gap_clusters_workspace_status", table_name="gap_clusters")
    op.drop_index("ix_conversation_analysis_workspace_created", table_name="conversation_analysis")
    op.drop_index("ix_conversations_chatbot_status_created", table_name="conversations")
    op.drop_index("ix_conversations_workspace_created", table_name="conversations")
