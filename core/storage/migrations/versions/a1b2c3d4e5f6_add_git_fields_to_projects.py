"""Add git URL, branch, files count, entities count, languages, and indexed timestamps to projects

Revision ID: a1b2c3d4e5f6
Revises: b7e18a4c9210
Create Date: 2026-06-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "b7e18a4c9210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new columns
    op.add_column("projects", sa.Column("git_url", sa.String(length=2048), nullable=True))
    op.add_column("projects", sa.Column("branch", sa.String(length=255), nullable=True))
    op.add_column("projects", sa.Column("files_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("entities_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("languages", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("last_reindexed_at", sa.DateTime(timezone=True), nullable=True))
    
    # Modify root to be nullable
    op.execute("ALTER TABLE projects ALTER COLUMN root DROP NOT NULL")
    # Drop unique constraint on root
    op.drop_constraint("projects_root_key", "projects", type_="unique")


def downgrade() -> None:
    # Revert root back to non-nullable and add back unique constraint
    op.create_unique_constraint("projects_root_key", "projects", ["root"])
    op.execute("ALTER TABLE projects ALTER COLUMN root SET NOT NULL")
    
    # Drop new columns
    op.drop_column("projects", "last_reindexed_at")
    op.drop_column("projects", "indexed_at")
    op.drop_column("projects", "languages")
    op.drop_column("projects", "entities_count")
    op.drop_column("projects", "files_count")
    op.drop_column("projects", "branch")
    op.drop_column("projects", "git_url")
