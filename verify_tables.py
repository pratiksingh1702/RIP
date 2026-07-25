import asyncio, sys
sys.path.insert(0, 'gateway')
from gateway.storage.database import engine
from sqlalchemy import text

async def verify():
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename"))
        tables = [row[0] for row in r.fetchall()]

        print('\n  All tables in Postgres public schema:')
        print('  ' + '-' * 40)

        expected = [
            'workspace_memory', 'workspace_knowledge', 'workspace_goals',
            'workspace_entities', 'entity_relationships',
            'route_cache', 'index_state',
            'sandbox_sessions', 'sandbox_snapshots', 'sandbox_command_log',
            'sessions', 'session_events', 'feedback', 'source_health',
            'registered_sources', 'source_credentials',
            'events', 'workflow_drafts', 'workflow_wires', 'workflow_runs',
            'workflow_policies', 'prompt_templates',
            'oauth_providers', 'pending_oauth_requests', 'oauth_tokens',
            'user_oauth_tokens', 'source_project_links',
            'gateway_settings', 'audit_logs'
        ]

        found = 0
        missing = 0
        for table in expected:
            if table in tables:
                print(f'    [OK] {table}')
                found += 1
            else:
                print(f'    [MISSING] {table}')
                missing += 1

        extra = [t for t in tables if t not in expected and t not in (
            'alembic_version', 'gateway_alembic_version', 'projects', 'api_keys',
            'file_hashes', 'index_state_table', 'embedding_cache', 'analysis_jobs',
            'users', 'organizations'
        )]
        if extra:
            print(f'\n  Extra tables: {extra}')

        print(f'\n  Summary: {found} found, {missing} missing out of {len(expected)} expected')

asyncio.run(verify())
