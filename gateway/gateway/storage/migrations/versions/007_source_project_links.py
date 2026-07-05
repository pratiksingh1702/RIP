"""Add source project allocation links.

Revision ID: 007
Revises: 006
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_project_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_oauth_token_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_oauth_token_id"], ["user_oauth_tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_oauth_token_id", "project_id", name="uq_source_project_link_token_project"),
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, project_id
            FROM user_oauth_tokens
            WHERE project_id IS NOT NULL AND project_id <> ''
            """
        )
    ).mappings()
    for row in rows:
        connection.execute(
            sa.text(
                """
                INSERT INTO source_project_links (id, user_oauth_token_id, project_id, created_at)
                VALUES (gen_random_uuid(), :token_id, :project_id, now())
                ON CONFLICT DO NOTHING
                """
            ),
            {"token_id": row["id"], "project_id": row["project_id"]},
        )


def downgrade() -> None:
    op.drop_table("source_project_links")
