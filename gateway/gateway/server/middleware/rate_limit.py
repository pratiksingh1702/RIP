"""Rate limiting middleware."""

import structlog
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from gateway.core.cache.redis_store import get_redis_store

logger = structlog.get_logger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to rate limit requests using Redis."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/metrics"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        
        redis = await get_redis_store()
        
        # If redis is not available, fail open or closed? 
        # For production readiness, let's log and allow but alert.
        if not redis._redis:
            logger.warning("Redis not available for rate limiting, allowing request", client_ip=client_ip)
            return await call_next(request)

        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 60)
            
            if count > self.requests_per_minute:
                logger.warning("Rate limit exceeded", client_ip=client_ip, count=count)
                raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
            
            return await call_next(request)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Rate limiting error", error=str(e))
            return await call_next(request)
