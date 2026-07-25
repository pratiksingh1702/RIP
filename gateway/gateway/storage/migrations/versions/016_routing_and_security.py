"""Add routing and security tables + domain columns."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '016_routing_and_security'
down_revision: Union[str, None] = '013_workflow_canvas_core'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('route_cache',
        sa.Column('cache_key', sa.String(16), primary_key=True),
        sa.Column('normalized_query', sa.Text, nullable=False),
        sa.Column('project_id', sa.String(255), nullable=False),
        sa.Column('workspace_id', sa.String(255), nullable=False),
        sa.Column('user_role', sa.String(50), nullable=False),
        sa.Column('routed_path', sa.String(20), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('suggested_sources', sa.JSON, server_default='[]'),
        sa.Column('needs_llm', sa.Boolean, server_default='0'),
        sa.Column('cached_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_route_cache_expires', 'route_cache', ['expires_at'])
    op.create_index('idx_route_cache_project', 'route_cache', ['project_id'])
    op.create_table('index_state',
        sa.Column('project_id', sa.String(255), primary_key=True),
        sa.Column('last_indexed_at', sa.DateTime(timezone=True)),
        sa.Column('last_commit_sha', sa.String(40)),
        sa.Column('is_warm', sa.Boolean, server_default='0'),
        sa.Column('index_duration_ms', sa.Integer),
        sa.Column('files_count', sa.Integer, server_default='0'),
        sa.Column('entities_count', sa.Integer, server_default='0'),
    )
    op.add_column('workspace_memory', sa.Column('domain', sa.String(100)))
    op.create_index('idx_workspace_memory_domain', 'workspace_memory', ['workspace_id', 'domain'])
    op.add_column('workspace_knowledge', sa.Column('domain', sa.String(100)))
    op.create_index('idx_workspace_knowledge_domain', 'workspace_knowledge', ['workspace_id', 'domain'])

def downgrade() -> None:
    op.drop_index('idx_workspace_knowledge_domain')
    op.drop_column('workspace_knowledge', 'domain')
    op.drop_index('idx_workspace_memory_domain')
    op.drop_column('workspace_memory', 'domain')
    op.drop_table('index_state')
    op.drop_table('route_cache')
