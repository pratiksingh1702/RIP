"""API Key management utilities."""

from __future__ import annotations

import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage.models import ApiKey

try:
    # Python 3.11+
    UTC = datetime.UTC
except AttributeError:
    # Older Python versions
    UTC = timezone.utc  # noqa: UP017


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a new API key.
    
    Returns:
        Tuple of (full_key, key_prefix, key_hash)
    """
    # Generate a random key
    key_bytes = secrets.token_bytes(32)
    key = "rip_" + secrets.token_urlsafe(32)
    
    # Extract prefix for identification
    prefix = key[:10]  # First 10 chars: "rip_xxxxxx"
    
    # Hash the key for storage
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    
    return key, prefix, key_hash


async def create_api_key(
    session: AsyncSession,
    name: str,
    description: str | None = None,
    expires_in_days: int | None = None,
    project_id: str | None = None,
) -> Tuple[str, ApiKey]:
    """
    Create a new API key in the database.
    
    Args:
        session: Database session
        name: Human-readable name for the key
        description: Optional description
        expires_in_days: Optional number of days until key expires
        project_id: Optional project ID to associate with the key
    
    Returns:
        Tuple of (plaintext_key, api_key_object)
    """
    plaintext_key, prefix, key_hash = generate_api_key()
    
    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
    
    api_key = ApiKey(
        name=name,
        key_hash=key_hash,
        prefix=prefix,
        is_active=True,
        expires_at=expires_at,
        description=description,
        project_id=project_id,
    )
    
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    
    return plaintext_key, api_key


async def verify_api_key(
    session: AsyncSession,
    plaintext_key: str,
) -> ApiKey | None:
    """
    Verify an API key and update last_used_at.
    
    Args:
        session: Database session
        plaintext_key: The API key to verify
    
    Returns:
        ApiKey object if valid, None otherwise
    """
    key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
    
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.key_hash == key_hash)
        .where(ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    
    if api_key:
        # Check if expired
        if api_key.expires_at and datetime.now(UTC) > api_key.expires_at:
            return None
        
        # Update last used time
        await session.execute(
            update(ApiKey)
            .where(ApiKey.id == api_key.id)
            .values(last_used_at=datetime.now(UTC))
        )
        await session.commit()
        
        return api_key
    
    return None


async def list_api_keys(session: AsyncSession) -> list[ApiKey]:
    """List all API keys."""
    result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return list(result.scalars().all())


async def revoke_api_key(session: AsyncSession, api_key_id: int) -> bool:
    """Revoke an API key."""
    result = await session.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key_id)
        .values(is_active=False)
    )
    await session.commit()
    return result.rowcount > 0
