"""Redis cache wrapper."""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from server.config import get_settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Async Redis cache wrapper with graceful fallback on connection issues."""

    def __init__(self, redis_url: str | None = None):
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self._client: aioredis.Redis | None = None
        self._is_available = True

    async def _get_client(self) -> aioredis.Redis | None:
        if not self._is_available:
            return None
        if self._client is None:
            try:
                self._client = aioredis.from_url(self.redis_url, decode_responses=True)
                await self._client.ping()
            except Exception as e:
                logger.warning(f"Redis not available at {self.redis_url}: {e}. Disabling cache.")
                self._is_available = False
                self._client = None
        return self._client

    async def get(self, key: str) -> str | None:
        """Get cache value."""
        client = await self._get_client()
        if client is None:
            return None
        try:
            return await client.get(key)
        except Exception as e:
            logger.error(f"Error getting key {key} from Redis: {e}")
            return None

    async def set(self, key: str, value: str, expire_seconds: int | None = None) -> bool:
        """Set cache value with optional expiration."""
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.set(key, value, ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Error setting key {key} in Redis: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting key {key} from Redis: {e}")
            return False

    async def close(self) -> None:
        """Close connection."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
