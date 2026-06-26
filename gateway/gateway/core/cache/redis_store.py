"""Redis store for caching and rate limiting."""

import redis.asyncio as redis
import structlog

from gateway.config import settings

logger = structlog.get_logger(__name__)

class RedisStore:
    """Async Redis store."""

    def __init__(self):
        self._redis: redis.Redis | None = None

    async def connect(self):
        """Connect to Redis."""
        if not settings.redis_url:
            return
        try:
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            self._redis = None

    async def get(self, key: str) -> str | None:
        """Get value from Redis."""
        if not self._redis:
            return None
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        """Set value in Redis."""
        if not self._redis:
            return
        await self._redis.set(key, value, ex=ex)

    async def incr(self, key: str) -> int:
        """Increment value in Redis."""
        if not self._redis:
            return 0
        return await self._redis.incr(key)

    async def expire(self, key: str, seconds: int):
        """Set expiration for key."""
        if not self._redis:
            return
        await self._redis.expire(key, seconds)

# Global redis instance
_redis_store: RedisStore | None = None

async def get_redis_store() -> RedisStore:
    """Get the global redis store."""
    global _redis_store
    if _redis_store is None:
        _redis_store = RedisStore()
        await _redis_store.connect()
    return _redis_store
