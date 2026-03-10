"""add sso_configs table

Revision ID: add_sso_configs
Revises: add_workspace_webhooks
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "add_sso_configs"
down_revision = "add_workspace_webhooks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sso_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_name", sa.String(255), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("client_secret", sa.Text, nullable=False),  # Fernet-encrypted
        sa.Column("discovery_url", sa.Text, nullable=False),  # OIDC /.well-known/openid-configuration
        sa.Column("email_domain", sa.String(255), nullable=False),  # e.g. "company.com"
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_sso_configs_workspace_id", "sso_configs", ["workspace_id"])
    op.create_index("ix_sso_configs_email_domain", "sso_configs", ["email_domain"])


def downgrade():
    op.drop_index("ix_sso_configs_email_domain", table_name="sso_configs")
    op.drop_index("ix_sso_configs_workspace_id", table_name="sso_configs")
    op.drop_table("sso_configs")
