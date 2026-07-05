"""Add events table and usable_as column to registered_sources.

Revision ID: 008
Revises: 007
Create Date: 2026-07-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Add usable_as column to registered_sources
    source_columns = {column["name"] for column in inspector.get_columns("registered_sources")}
    if "usable_as" not in source_columns:
        usable_as_type = (
            sa.ARRAY(sa.Text())
            if bind.dialect.name == "postgresql"
            else sa.JSON()
        )
        op.add_column(
            "registered_sources",
            sa.Column("usable_as", usable_as_type, nullable=True),
        )

    # Create events table
    if "events" not in inspector.get_table_names():
        op.create_table(
            "events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("org_id", sa.String(length=255), nullable=True),
            sa.Column("project_id", sa.String(length=255), nullable=True),
            sa.Column("session_id", sa.String(length=255), nullable=True),
            sa.Column("workflow_run_id", sa.String(length=255), nullable=True),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("source_block_id", sa.String(length=100), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    # Set default value for existing rows
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                UPDATE registered_sources
                SET usable_as = ARRAY['retrieval']::TEXT[]
                WHERE usable_as IS NULL
                """
            )
        )
    else:
        bind.execute(
            sa.text(
                """
                UPDATE registered_sources
                SET usable_as = '["retrieval"]'
                WHERE usable_as IS NULL
                """
            )
        )


def downgrade() -> None:
    op.drop_table("events")
    op.drop_column("registered_sources", "usable_as")
