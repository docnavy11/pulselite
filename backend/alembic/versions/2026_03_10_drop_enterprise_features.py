"""drop enterprise features

Revision ID: drop_enterprise_features
Revises: add_workspace_openrouter
Create Date: 2026-03-10

"""

import sqlalchemy as sa
from alembic import op

revision = "drop_enterprise_features"
down_revision = "add_workspace_openrouter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop FK columns from conversations first (before dropping parent tables)
    op.drop_column("conversations", "inbox_id")
    op.drop_column("conversations", "team_id")
    op.drop_column("conversations", "sla_policy_id")
    op.drop_column("conversations", "snoozed_until")
    op.drop_column("conversations", "waiting_since")
    op.drop_column("conversations", "intercom_id")
    op.drop_column("conversations", "external_id")

    # Drop enterprise tables (FK references removed above)
    op.drop_table("action_events")
    op.drop_table("chatbot_actions")
    op.drop_table("tickets")
    op.drop_table("api_keys")
    op.drop_table("audit_logs")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_table("inboxes")
    op.drop_table("intelligence_signals")
    op.drop_table("lead_scores")
    op.drop_table("topic_clusters")
    op.drop_table("autonomous_resolution_stats")
    op.drop_table("sso_configs")

    # Drop columns from workspaces
    op.drop_column("workspaces", "white_label_enabled")
    op.drop_column("workspaces", "intercom_app_id")

    # Drop columns from messages
    op.drop_column("messages", "intercom_part_id")

    # Drop columns from conversation_analysis
    op.drop_column("conversation_analysis", "lead_intent")
    op.drop_column("conversation_analysis", "feature_requests")
    op.drop_column("conversation_analysis", "bug_reports")
    op.drop_column("conversation_analysis", "competitor_mentions")
    op.drop_column("conversation_analysis", "expansion_signals")
    op.drop_column("conversation_analysis", "churn_signals")
    op.drop_column("conversation_analysis", "customer_effort_score")
    op.drop_column("conversation_analysis", "action_items")

    # Drop columns from agents
    op.drop_column("agents", "has_inbox_seat")
    op.drop_column("agents", "availability")

    # Drop columns from gap_clusters
    op.drop_column("gap_clusters", "draft_article_id")
    op.drop_column("gap_clusters", "resolution_impact")

    # Drop column from retrieval_logs
    op.drop_column("retrieval_logs", "query_embedding_model")


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for this destructive migration")
