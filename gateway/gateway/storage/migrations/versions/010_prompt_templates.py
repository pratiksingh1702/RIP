"""Add prompt templates table.

Revision ID: 010
Revises: 009
Create Date: 2026-07-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "prompt_templates" not in inspector.get_table_names():
        op.create_table(
            "prompt_templates",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("version", sa.String(length=50), nullable=False, server_default="1.0.0"),
            sa.Column("system_prompt", sa.Text(), nullable=True),
            sa.Column("prompt_template", sa.Text(), nullable=False),
            sa.Column("variables", sa.JSON(), nullable=True),
            sa.Column("owner_org", sa.String(length=255), nullable=True),
            sa.Column("visibility", sa.String(length=50), nullable=False, server_default="private"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("prompt_templates")
