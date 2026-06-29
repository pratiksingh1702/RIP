"""API Key Authentication Middleware"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_keys import verify_api_key as verify_api_key_from_db
from core.storage.database import get_db_session
from core.storage.models import ApiKey


def get_valid_env_api_keys() -> set[str]:
    """Load valid API keys from environment variable (fallback)."""
    keys_str = os.getenv("RIP_API_KEYS", "")
    if not keys_str:
        return set()
    return set(k.strip() for k in keys_str.split(",") if k.strip())


async def verify_api_key(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """
    Middleware: verify API key in Authorization header.
    First checks database, then falls back to environment variable keys.
    If no keys configured at all, allows all requests (development mode).
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        # Check if we have any keys configured
        env_keys = get_valid_env_api_keys()
        # We'll check DB keys below, but first handle missing header
        
        # For now, if no auth header and no env keys, let's proceed to check DB count
        # But actually, let's follow the flow properly
        pass
    else:
        provided_key = auth_header[7:]  # Remove "Bearer "
        
        # First try to verify from database
        api_key = await verify_api_key_from_db(db, provided_key)
        if api_key:
            request.state.api_key = api_key
            request.state.api_key_scope = "all"
            api_key._rip_access_scope = request.state.api_key_scope
            return
        
        # Then fall back to environment variable keys
        env_keys = get_valid_env_api_keys()
        if provided_key in env_keys:
            request.state.api_key = ApiKey(
                name="Env Key",
                key_hash="",
                prefix=provided_key[:10],
                is_active=True,
                project_id=None
            )
            request.state.api_key_scope = "all"
            request.state.api_key._rip_access_scope = "all"
            return

    # If we got here, check if we have any keys configured at all
    env_keys = get_valid_env_api_keys()
    
    # If no keys configured, allow development mode
    if not env_keys:
        # Also check if there are any active keys in DB
        result = await db.execute(select(ApiKey).where(ApiKey.is_active.is_(True)).limit(1))
        has_db_keys = result.scalar_one_or_none() is not None
        
        if not has_db_keys:
            # No keys configured at all - development mode
            request.state.api_key = ApiKey(
                name="Dev Mode Key",
                key_hash="",
                prefix="dev",
                is_active=True,
                project_id=None
            )
            request.state.api_key_scope = "all"
            request.state.api_key._rip_access_scope = "all"
            return
    
    # Otherwise, require authentication
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include 'Authorization: Bearer YOUR_KEY' header."
        )
    
    raise HTTPException(
        status_code=403,
        detail="Invalid API key."
    )
