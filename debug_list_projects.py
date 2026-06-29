import asyncio
from core.storage.database import async_session_factory
from core.projects import list_projects

async def test_list_projects():
    try:
        async with async_session_factory() as session:
            projects = await list_projects(session)
            print(f"Found {len(projects)} projects")
            for p in projects:
                print(f"Project: {p.id}, {p.name}, indexed_at: {p.indexed_at}")
                # Simulate the mapping in the router
                data = {
                    "project_id": p.id,
                    "project_name": p.name,
                    "indexed_at": p.indexed_at.isoformat() if p.indexed_at else "",
                    "files_count": p.files_count or 0,
                    "entities_count": p.entities_count or 0,
                    "languages": p.languages or [],
                    "git_url": p.git_url,
                    "branch": p.branch,
                }
                print(f"Mapped data: {data}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_list_projects())
