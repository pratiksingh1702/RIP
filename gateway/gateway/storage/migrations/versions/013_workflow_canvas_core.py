"""Add workflow canvas core fields and wires.

Revision ID: 013
Revises: 012
Create Date: 2026-07-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    inspector = inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("registered_sources", sa.Column("block_display", sa.JSON(), nullable=True))
    _add_column_if_missing("workflow_drafts", sa.Column("description", sa.Text(), nullable=True))
    _add_column_if_missing("workflow_drafts", sa.Column("category", sa.String(length=50), nullable=True))
    _add_column_if_missing(
        "workflow_drafts",
        sa.Column("version", sa.String(length=20), nullable=False, server_default="1.0.0"),
    )
    _add_column_if_missing(
        "workflow_drafts",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="draft"),
    )
    _add_column_if_missing("workflow_drafts", sa.Column("source_template_id", sa.String(length=255), nullable=True))
    _add_column_if_missing("workflow_drafts", sa.Column("canvas_state", sa.JSON(), nullable=True))
    _add_column_if_missing(
        "workflow_drafts",
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="private"),
    )
    _add_column_if_missing(
        "workflow_drafts",
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing("workflow_drafts", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("workflow_drafts", sa.Column("avg_duration_ms", sa.Integer(), nullable=True))

    inspector = inspect(op.get_bind())
    if "workflow_wires" not in inspector.get_table_names():
        op.create_table(
            "workflow_wires",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("workflow_id", sa.UUID(), nullable=False),
            sa.Column("source_step_id", sa.String(length=100), nullable=False),
            sa.Column("source_port", sa.String(length=50), nullable=False, server_default="output"),
            sa.Column("target_step_id", sa.String(length=100), nullable=False),
            sa.Column("target_port", sa.String(length=50), nullable=False),
            sa.Column("mapping", sa.JSON(), nullable=True),
            sa.Column("wire_color", sa.String(length=7), nullable=False, server_default="#3B82F6"),
            sa.Column("label", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflow_drafts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "workflow_id",
                "source_step_id",
                "source_port",
                "target_step_id",
                "target_port",
                name="uq_workflow_wire_ports",
            ),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "workflow_wires" in inspector.get_table_names():
        op.drop_table("workflow_wires")
    for column_name in (
        "avg_duration_ms",
        "last_run_at",
        "run_count",
        "visibility",
        "canvas_state",
        "source_template_id",
        "source",
        "version",
        "category",
        "description",
    ):
        columns = {item["name"] for item in inspector.get_columns("workflow_drafts")}
        if column_name in columns:
            op.drop_column("workflow_drafts", column_name)
    columns = {item["name"] for item in inspector.get_columns("registered_sources")}
    if "block_display" in columns:
        op.drop_column("registered_sources", "block_display")
