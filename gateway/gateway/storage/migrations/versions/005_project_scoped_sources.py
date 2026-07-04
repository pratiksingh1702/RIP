"""Add project scope to registered sources.

Revision ID: 005
Revises: 004
Create Date: 2026-07-04 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("registered_sources", sa.Column("project_id", sa.String(length=255), nullable=True))
    try:
        op.drop_constraint("registered_sources_name_key", "registered_sources", type_="unique")
    except Exception:
        pass
    op.create_unique_constraint(
        "uq_registered_source_project_name",
        "registered_sources",
        ["project_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_registered_source_project_name", "registered_sources", type_="unique")
    op.create_unique_constraint("registered_sources_name_key", "registered_sources", ["name"])
    op.drop_column("registered_sources", "project_id")
