"""Add projects table

Revision ID: b7e18a4c9210
Revises: abc123456789
Create Date: 2026-06-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e18a4c9210"
down_revision: str | None = "abc123456789"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("root", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("root"),
    )


def downgrade() -> None:
    op.drop_table("projects")
