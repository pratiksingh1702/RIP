"""Add per-user project OAuth scope.

Revision ID: 006
Revises: 005
Create Date: 2026-07-04 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pending_oauth_requests", sa.Column("user_id", sa.String(length=255), nullable=True))
    op.add_column("pending_oauth_requests", sa.Column("project_id", sa.String(length=255), nullable=True))
    op.create_table(
        "user_oauth_tokens",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("project_id", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(length=40), nullable=True),
        sa.Column("account_label", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["provider_id"], ["oauth_providers.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["registered_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "user_id", "project_id", name="uq_user_oauth_source_user_project"),
    )
    op.alter_column("user_oauth_tokens", "project_id", server_default=None)


def downgrade() -> None:
    op.drop_table("user_oauth_tokens")
    op.drop_column("pending_oauth_requests", "project_id")
    op.drop_column("pending_oauth_requests", "user_id")
