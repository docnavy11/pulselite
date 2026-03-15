"""Add intelligence_config to workspaces and FK on gap_events.gap_cluster_id

Revision ID: 20260313_intel
Revises: None (run after latest)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260313_intel"
down_revision = "610382505390"
branch_labels = None
depends_on = None

DEFAULT_CONFIG = '{"auto_analyze": true, "sentiment_trends": true, "gap_clustering": true}'


def upgrade() -> None:
    # Add intelligence_config column
    op.add_column(
        "workspaces",
        sa.Column(
            "intelligence_config",
            JSONB,
            server_default=sa.text(f"'{DEFAULT_CONFIG}'::jsonb"),
            nullable=False,
        ),
    )

    # Add FK on gap_events.gap_cluster_id (was missing)
    op.create_foreign_key(
        "fk_gap_events_gap_cluster_id",
        "gap_events",
        "gap_clusters",
        ["gap_cluster_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_gap_events_gap_cluster_id", "gap_events", type_="foreignkey")
    op.drop_column("workspaces", "intelligence_config")
