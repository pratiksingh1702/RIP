"""Add OAuth bridge tables.

Revision ID: 003
Revises: 002
Create Date: 2026-07-03 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_providers",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("authorize_url", sa.Text(), nullable=False),
        sa.Column("token_url", sa.Text(), nullable=False),
        sa.Column("revoke_url", sa.Text(), nullable=True),
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("client_secret", sa.Text(), nullable=False),
        sa.Column("default_scopes", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("supports_pkce", sa.Boolean(), nullable=False),
        sa.Column("icon_key", sa.String(length=80), nullable=False),
        sa.Column("allowed_redirect_uris", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pending_oauth_requests",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=160), nullable=False),
        sa.Column("code_verifier", sa.Text(), nullable=True),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("client_type", sa.String(length=20), nullable=False),
        sa.Column("requested_by", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["oauth_providers.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["registered_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state"),
    )
    op.create_table(
        "oauth_tokens",
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", sa.String(length=80), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(length=40), nullable=False),
        sa.Column("account_label", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["oauth_providers.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["registered_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id"),
        sa.UniqueConstraint("provider_id", "account_label", name="uq_oauth_provider_account_label"),
    )


def downgrade() -> None:
    op.drop_table("oauth_tokens")
    op.drop_table("pending_oauth_requests")
    op.drop_table("oauth_providers")
