"""Add prompt id to feedback.

Revision ID: 012
Revises: 011
Create Date: 2026-07-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("feedback")}
    if "prompt_id" not in columns:
        op.add_column("feedback", sa.Column("prompt_id", sa.UUID(), nullable=True))


def downgrade() -> None:
    op.drop_column("feedback", "prompt_id")
