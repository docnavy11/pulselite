"""Initial schema with all 28 tables

Revision ID: 001
Revises:
Create Date: 2026-03-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"vector\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"pg_trgm\"")

    # 1. workspaces
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), unique=True, nullable=False),
        sa.Column("plan", sa.Text(), server_default=sa.text("'free'")),
        sa.Column("plan_conversation_cap", sa.Integer(), server_default=sa.text("100")),
        sa.Column("timezone", sa.Text(), server_default=sa.text("'UTC'")),
        sa.Column("primary_language", sa.Text(), server_default=sa.text("'en'")),
        sa.Column("intercom_app_id", sa.Text(), nullable=True),
        sa.Column("webhook_secret", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 2. agents
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("has_inbox_seat", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("availability", sa.Text(), server_default=sa.text("'online'")),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("google_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("workspace_id", "email"),
    )

    # 3. workspace_memberships
    op.create_table(
        "workspace_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'member'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 4. teams
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 5. team_members
    op.create_table(
        "team_members",
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), primary_key=True),
        sa.Column("priority_level", sa.Integer(), server_default=sa.text("1")),
    )

    # 6. inboxes
    op.create_table(
        "inboxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("channel_type", sa.Text(), server_default=sa.text("'web_widget'")),
        sa.Column("channel_config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_inbox_seat_required", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 7. companies
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("company_size", sa.Integer(), nullable=True),
        sa.Column("monthly_spend", sa.Numeric(12, 2), nullable=True),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("intercom_id", sa.Text(), nullable=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("custom_attributes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 8. contacts
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("contact_type", sa.Text(), server_default=sa.text("'visitor'")),
        sa.Column("lifecycle_stage", sa.Text(), server_default=sa.text("'unknown'")),
        sa.Column("intercom_id", sa.Text(), nullable=True),
        sa.Column("crm_contact_id", sa.Text(), nullable=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("browser", sa.Text(), nullable=True),
        sa.Column("os", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lead_score", sa.Integer(), server_default=sa.text("0")),
        sa.Column("lead_tier", sa.Text(), nullable=True),
        sa.Column("churn_risk", sa.Text(), nullable=True),
        sa.Column("expansion_potential", sa.Text(), nullable=True),
        sa.Column("custom_attributes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("workspace_id", "email"),
        sa.UniqueConstraint("workspace_id", "intercom_id"),
    )

    # 9. contact_events
    op.create_table(
        "contact_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 10. data_attributes
    op.create_table(
        "data_attributes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("data_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("workspace_id", "model", "name"),
    )

    # 11. segments
    op.create_table(
        "segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("filter_rules", postgresql.JSONB(), nullable=False),
        sa.Column("person_type", sa.Text(), server_default=sa.text("'contact'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 12. chatbots
    op.create_table(
        "chatbots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), server_default=sa.text("'Assistant'")),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("tone", sa.Text(), server_default=sa.text("'professional'")),
        sa.Column("language", sa.Text(), server_default=sa.text("'en'")),
        sa.Column("llm_provider", sa.Text(), server_default=sa.text("'openai'")),
        sa.Column("llm_model", sa.Text(), server_default=sa.text("'gpt-4o-mini'")),
        sa.Column("byoak", sa.Text(), nullable=True),
        sa.Column("temperature", sa.Float(), server_default=sa.text("0.3")),
        sa.Column("max_tokens", sa.Integer(), server_default=sa.text("1000")),
        sa.Column("confidence_threshold", sa.Float(), server_default=sa.text("0.65")),
        sa.Column("retrieval_top_k", sa.Integer(), server_default=sa.text("5")),
        sa.Column("use_reranking", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("use_hybrid_retrieval", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("presales_kb_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("postsales_kb_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fallback_type", sa.Text(), server_default=sa.text("'escalate'")),
        sa.Column("fallback_message", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 13. knowledge_bases
    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("chatbot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chatbots.id"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kb_type", sa.Text(), server_default=sa.text("'general'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 14. documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'")),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_frequency", sa.Text(), server_default=sa.text("'weekly'")),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 15. article_collections
    op.create_table(
        "article_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("article_collections.id"), nullable=True),
        sa.Column("collection_type", sa.Text(), server_default=sa.text("'collection'")),
        sa.Column("order_index", sa.Integer(), server_default=sa.text("0")),
        sa.Column("intercom_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 16. articles
    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("article_collections.id"), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), server_default=sa.text("'draft'")),
        sa.Column("is_ai_drafted", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("gap_cluster_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("views_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("helpful_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("not_helpful_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("parent_id", sa.Text(), nullable=True),
        sa.Column("parent_type", sa.Text(), nullable=True),
        sa.Column("intercom_id", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), server_default=sa.text("'en'")),
        sa.Column("order_index", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 17. conversations
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("inbox_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inboxes.id"), nullable=True),
        sa.Column("chatbot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chatbots.id"), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'open'")),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waiting_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Text(), server_default=sa.text("'normal'")),
        sa.Column("channel", sa.Text(), server_default=sa.text("'chat'")),
        sa.Column("lifecycle_stage", sa.Text(), server_default=sa.text("'unknown'")),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_title", sa.Text(), nullable=True),
        sa.Column("confidence_avg", sa.Float(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("ai_participated", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("autonomous_resolved", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("sla_policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("intercom_id", sa.Text(), nullable=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 18. messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("message_type", sa.Text(), nullable=False),
        sa.Column("author_type", sa.Text(), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("part_type", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), server_default=sa.text("'text'")),
        sa.Column("attachments", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.Text(), server_default=sa.text("'sent'")),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("retrieval_log_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_fallback", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("intercom_part_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 19. tags
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), server_default=sa.text("'#6366f1'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("workspace_id", "name"),
    )

    # 20. conversation_tags
    op.create_table(
        "conversation_tags",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), primary_key=True),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tags.id"), primary_key=True),
        sa.Column("applied_by_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 21. tickets
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("ticket_state", sa.Text(), server_default=sa.text("'submitted'")),
        sa.Column("ticket_type_category", sa.Text(), server_default=sa.text("'customer'")),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("custom_attributes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("intercom_ticket_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 22. retrieval_logs
    op.create_table(
        "retrieval_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("chatbot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chatbots.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_embedding_model", sa.Text(), server_default=sa.text("'text-embedding-3-small'")),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("confidence_avg", sa.Float(), nullable=True),
        sa.Column("retrieved_chunk_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("reranked", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("escalated", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("response_generated", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("retrieval_ms", sa.Integer(), nullable=True),
        sa.Column("generation_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 23. gap_events
    op.create_table(
        "gap_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("retrieval_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("retrieval_logs.id"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("gap_cluster_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 24. gap_clusters
    op.create_table(
        "gap_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("chatbot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chatbots.id"), nullable=True),
        sa.Column("topic_label", sa.Text(), nullable=False),
        sa.Column("topic_keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("gap_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("representative_query", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'open'")),
        sa.Column("draft_article_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_impact", sa.Float(), nullable=True),
        sa.Column("clustered_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 25. intelligence_signals
    op.create_table(
        "intelligence_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("actioned", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_signals_type", "intelligence_signals", ["workspace_id", "signal_type", "created_at"])

    # 26. topic_clusters
    op.create_table(
        "topic_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("chatbot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chatbots.id"), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("conversation_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("volume_trend", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("anomaly_detected", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("anomaly_type", sa.Text(), nullable=True),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 27. lead_scores
    op.create_table(
        "lead_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tier", sa.Text(), nullable=True),
        sa.Column("signals", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("crm_pushed", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("crm_pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("slack_alerted", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # 28. conversation_analysis
    op.create_table(
        "conversation_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), unique=True, nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_label", sa.Text(), nullable=True),
        sa.Column("intent_primary", sa.Text(), nullable=True),
        sa.Column("intent_secondary", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("outcome_category", sa.Text(), nullable=True),
        sa.Column("lead_intent", sa.Text(), nullable=True),
        sa.Column("feature_requests", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("bug_reports", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("competitor_mentions", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("expansion_signals", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("churn_signals", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("topics", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("customer_effort_score", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("action_items", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("llm_model", sa.Text(), server_default=sa.text("'gpt-4o-mini'")),
        sa.Column("processing_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # 29. autonomous_resolution_stats (table 27 from data model + workspace_memberships = 28 total)
    op.create_table(
        "autonomous_resolution_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("chatbot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chatbots.id"), nullable=True),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("total_conversations", sa.Integer(), server_default=sa.text("0")),
        sa.Column("autonomously_resolved", sa.Integer(), server_default=sa.text("0")),
        sa.Column("escalated_to_human", sa.Integer(), server_default=sa.text("0")),
        sa.Column("abandoned", sa.Integer(), server_default=sa.text("0")),
        sa.Column("avg_confidence_score", sa.Float(), nullable=True),
        sa.Column("knowledge_velocity", sa.Float(), nullable=True),
        sa.Column("documentation_debt", sa.Integer(), nullable=True),
        sa.UniqueConstraint("workspace_id", "chatbot_id", "period_date"),
    )


def downgrade() -> None:
    op.drop_table("autonomous_resolution_stats")
    op.drop_table("conversation_analysis")
    op.drop_table("lead_scores")
    op.drop_table("topic_clusters")
    op.drop_index("idx_signals_type", table_name="intelligence_signals")
    op.drop_table("intelligence_signals")
    op.drop_table("gap_clusters")
    op.drop_table("gap_events")
    op.drop_table("retrieval_logs")
    op.drop_table("tickets")
    op.drop_table("conversation_tags")
    op.drop_table("tags")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("articles")
    op.drop_table("article_collections")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")
    op.drop_table("chatbots")
    op.drop_table("segments")
    op.drop_table("data_attributes")
    op.drop_table("contact_events")
    op.drop_table("contacts")
    op.drop_table("companies")
    op.drop_table("inboxes")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_table("workspace_memberships")
    op.drop_table("agents")
    op.drop_table("workspaces")
