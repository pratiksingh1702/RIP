"""Add dynamic source registry tables.

Revision ID: 002
Revises: 001
Create Date: 2026-07-03 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "registered_sources",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("transport", sa.String(length=20), nullable=False),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("auth_type", sa.String(length=50), nullable=False),
        sa.Column("credential_ref", sa.String(length=120), nullable=True),
        sa.Column("domain_hints", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("priority_hint", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("health_status", sa.String(length=30), nullable=False),
        sa.Column("protected", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "source_credentials",
        sa.Column("ref", sa.String(length=120), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("masked_value", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ref"),
    )
    op.create_table(
        "gateway_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("gateway_settings")
    op.drop_table("source_credentials")
    op.drop_table("registered_sources")
