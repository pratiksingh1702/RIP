"""Add workflow tables.

Revision ID: 009
Revises: 008
Create Date: 2026-07-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    # Create workflow_drafts table
    if "workflow_drafts" not in tables:
        op.create_table(
            "workflow_drafts",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("owner_user_id", sa.String(length=255), nullable=False),
            sa.Column("scope", sa.String(length=50), nullable=False, server_default="project"),
            sa.Column("project_id", sa.String(length=255), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
            sa.Column("blocks", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create workflow_runs table
    if "workflow_runs" not in tables:
        op.create_table(
            "workflow_runs",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("draft_id", sa.UUID(), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
            sa.Column("state", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["draft_id"], ["workflow_drafts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("workflow_runs")
    op.drop_table("workflow_drafts")
