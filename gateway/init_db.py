import asyncio
from gateway.storage.database import ensure_storage_schema
from gateway.core.oauth import ensure_oauth_providers

async def main():
    await ensure_storage_schema()
    await ensure_oauth_providers()
    print("Database tables and OAuth providers initialized successfully!")

if __name__ == "__main__":
    asyncio.run(main())
