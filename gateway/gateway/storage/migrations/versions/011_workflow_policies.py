"""Add workflow policies table.

Revision ID: 011
Revises: 010
Create Date: 2026-07-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "workflow_policies" not in inspector.get_table_names():
        op.create_table(
            "workflow_policies",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("action", sa.String(length=120), nullable=False),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("allowed_repos", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("action", name="uq_workflow_policy_action"),
        )


def downgrade() -> None:
    op.drop_table("workflow_policies")
