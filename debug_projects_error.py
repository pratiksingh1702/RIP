import asyncio
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select
from core.storage.database import async_session_factory
from core.storage.models import ApiKey
from core.projects import list_projects

try:
    # Python 3.11+
    UTC = datetime.UTC
except AttributeError:
    # Older Python versions
    UTC = timezone.utc

async def debug_projects():
    plaintext_key = "rip_HPzvDrzd5QQ3Bk9pvzVuYie-zUI110Fly-x1KjRnMpQ"
    key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
    
    async with async_session_factory() as session:
        print("Step 1: Verifying API Key")
        result = await session.execute(
            select(ApiKey)
            .where(ApiKey.key_hash == key_hash)
            .where(ApiKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()
        if api_key:
            print(f"Found API Key: {api_key.name}, project_id: {api_key.project_id}")
            if api_key.expires_at:
                print(f"Key expires at: {api_key.expires_at} (tz: {api_key.expires_at.tzinfo})")
                now = datetime.now(UTC)
                print(f"Now: {now} (tz: {now.tzinfo})")
                try:
                    is_expired = now > api_key.expires_at
                    print(f"Is expired: {is_expired}")
                except Exception as e:
                    print(f"Comparison error: {e}")
        else:
            print("API Key not found or inactive")
            return

        print("\nStep 2: Calling list_projects")
        try:
            projects = await list_projects(session, associated_project_id=api_key.project_id)
            print(f"Found {len(projects)} projects")
        except Exception as e:
            print(f"list_projects error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_projects())
