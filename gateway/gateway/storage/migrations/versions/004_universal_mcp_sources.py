"""Add universal MCP source config.

Revision ID: 004
Revises: 003
Create Date: 2026-07-03 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "registered_sources",
        sa.Column("mcp_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.alter_column("registered_sources", "mcp_config", server_default=None)


def downgrade() -> None:
    op.drop_column("registered_sources", "mcp_config")
