"""Workspace Memory — the system's long-term memory of everything."""

revision = "014"
down_revision = "012"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "workspace_memory",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False, index=True),
        sa.Column("project_id", sa.String(36), nullable=True, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("query", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("result_data", sa.JSON, nullable=True),
        sa.Column("sources_used", sa.JSON, nullable=True),
        sa.Column("context_assembled", sa.Text, nullable=True),
        sa.Column("files_changed", sa.JSON, nullable=True),
        sa.Column("tokens_used", sa.Integer, default=0),
        sa.Column("tokens_budgeted", sa.Integer, default=0),
        sa.Column("duration_seconds", sa.Float, default=0),
        sa.Column("status", sa.String(20), default="completed"),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_wm_workspace", "workspace_memory", ["workspace_id", "category"])
    op.create_index("idx_wm_project", "workspace_memory", ["project_id"])
    op.create_index("idx_wm_created", "workspace_memory", ["created_at"])
    op.create_index("idx_wm_intent", "workspace_memory", ["workspace_id", "intent"])


def downgrade():
    op.drop_table("workspace_memory")
