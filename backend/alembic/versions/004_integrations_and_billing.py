"""integrations and billing

Revision ID: 004
Revises: 003
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_configs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("integration_type", sa.Text(), nullable=False),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("workspace_id", "integration_type"),
    )

    op.create_table(
        "credit_ledger",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.add_column("workspaces", sa.Column("onboarding_step", sa.Integer(), server_default=sa.text("1")))
    op.add_column("workspaces", sa.Column("onboarding_completed", sa.Boolean(), server_default=sa.text("FALSE")))
    op.add_column("workspaces", sa.Column("stripe_customer_id", sa.Text(), nullable=True))
    op.add_column("workspaces", sa.Column("stripe_subscription_id", sa.Text(), nullable=True))
    op.add_column("workspaces", sa.Column("credit_balance", sa.Integer(), server_default=sa.text("1000")))

    op.create_index("idx_credit_ledger_workspace", "credit_ledger", ["workspace_id"])
    op.create_index("idx_integration_configs_workspace", "integration_configs", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("idx_integration_configs_workspace")
    op.drop_index("idx_credit_ledger_workspace")
    op.drop_column("workspaces", "credit_balance")
    op.drop_column("workspaces", "stripe_subscription_id")
    op.drop_column("workspaces", "stripe_customer_id")
    op.drop_column("workspaces", "onboarding_completed")
    op.drop_column("workspaces", "onboarding_step")
    op.drop_table("credit_ledger")
    op.drop_table("integration_configs")
