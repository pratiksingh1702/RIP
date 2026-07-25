import asyncio, sys
sys.path.insert(0, 'gateway')
from gateway.core.sources.registry import get_source_registry

PROJECT_ID = 'fb8a1079-02b4-5355-9425-593637c4b2f0'

async def check():
    reg = get_source_registry()
    await reg.refresh(project_id=PROJECT_ID)
    names = reg.enabled_source_names(project_id=PROJECT_ID)
    print('Enabled sources:', names)
    print('Has workspace_memory:', 'workspace_memory' in names)
    print('Has workspace_knowledge:', 'workspace_knowledge' in names)
    for name in names:
        src = reg.get_source(name)
        label = type(src).__name__ if src else 'NOT FOUND'
        print(f'  {name}: {label}')

asyncio.run(check())
