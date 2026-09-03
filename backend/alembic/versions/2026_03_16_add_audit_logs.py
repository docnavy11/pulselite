"""Restructure audit_logs table with proper columns and indexes

Revision ID: 2026_03_16_audit
Revises: 63e7f147b8c4
Create Date: 2026-03-16

Safety: This migration does NOT drop and recreate the table. It checks whether
the table exists and either creates it fresh or alters the existing table to
match the target schema. This preserves existing audit data in production.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "2026_03_16_audit"
down_revision: Union[str, None] = "63e7f147b8c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the current database."""
    conn = op.get_bind()
    insp = inspect(conn)
    return table_name in insp.get_table_names()


def _get_column_names(table_name: str) -> set[str]:
    """Get existing column names for a table."""
    conn = op.get_bind()
    insp = inspect(conn)
    return {col["name"] for col in insp.get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists("audit_logs"):
        # Table does not exist — create it from scratch
        op.create_table(
            "audit_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
            sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
            sa.Column("user_email", sa.String(255), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("resource_type", sa.String(100), nullable=True),
            sa.Column("resource_id", sa.String(255), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("details", JSONB, nullable=True),
        )
    else:
        # Table already exists — add any missing columns
        existing = _get_column_names("audit_logs")

        if "timestamp" not in existing:
            op.add_column("audit_logs", sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False))
        if "user_id" not in existing:
            op.add_column("audit_logs", sa.Column("user_id", UUID(as_uuid=True), nullable=True))
            op.create_foreign_key("fk_audit_logs_user_id", "audit_logs", "agents", ["user_id"], ["id"], ondelete="SET NULL")
        if "user_email" not in existing:
            op.add_column("audit_logs", sa.Column("user_email", sa.String(255), nullable=True))
        if "details" not in existing:
            op.add_column("audit_logs", sa.Column("details", JSONB, nullable=True))

    # Create indexes idempotently
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp ON audit_logs (timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_workspace_id ON audit_logs (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_action")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_workspace_id")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_timestamp")
    op.drop_table("audit_logs")
