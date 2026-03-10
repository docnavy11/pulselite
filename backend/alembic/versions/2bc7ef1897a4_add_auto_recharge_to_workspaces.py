"""add_auto_recharge_to_workspaces

Revision ID: 2bc7ef1897a4
Revises: 005
Create Date: 2026-03-07 22:29:11.811489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2bc7ef1897a4'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column(
        "auto_recharge_enabled", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False
    ))
    op.add_column("workspaces", sa.Column(
        "auto_recharge_threshold", sa.Integer(), server_default=sa.text("200"), nullable=False
    ))
    op.add_column("workspaces", sa.Column(
        "auto_recharge_amount", sa.Integer(), server_default=sa.text("1000"), nullable=False
    ))


def downgrade() -> None:
    op.drop_column("workspaces", "auto_recharge_enabled")
    op.drop_column("workspaces", "auto_recharge_threshold")
    op.drop_column("workspaces", "auto_recharge_amount")
