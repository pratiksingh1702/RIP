"""Route Cache — TTL-based caching of routing decisions."""
from __future__ import annotations
import logging
from datetime import UTC, datetime
from gateway.core.router.models import RouteCacheKey, RouteCacheEntry, RouteDecision

logger = logging.getLogger(__name__)

class RouteCache:
    """In-memory cache for route decisions. TTL: 5 minutes."""

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, RouteCacheEntry] = {}
        self._ttl = ttl_seconds

    def get(self, key: RouteCacheKey) -> RouteDecision | None:
        """Get cached decision if valid."""
        cache_key = key.to_hash()
        entry = self._store.get(cache_key)
        if entry is None:
            return None
        if not entry.is_valid:
            del self._store[cache_key]
            return None
        logger.debug("Route cache hit: %s → %s", cache_key, entry.decision.path)
        return entry.decision

    def set(self, key: RouteCacheKey, decision: RouteDecision) -> None:
        """Cache a routing decision."""
        entry = RouteCacheEntry(key=key, decision=decision, cached_at=datetime.now(UTC), ttl_seconds=self._ttl)
        self._store[key.to_hash()] = entry
        logger.debug("Route cache set: %s → %s", key.to_hash(), decision.path)

    def invalidate_project(self, project_id: str) -> int:
        """Remove all cached entries for a project (called on git push)."""
        removed = 0
        to_remove = []
        for cache_key, entry in self._store.items():
            if entry.key.project_id == project_id:
                to_remove.append(cache_key)
        for k in to_remove:
            del self._store[k]
            removed += 1
        if removed:
            logger.info("Route cache invalidated: project=%s, removed=%d", project_id, removed)
        return removed

    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self._store)
        self._store.clear()
        logger.info("Route cache cleared: %d entries", count)

    @property
    def size(self) -> int:
        return len(self._store)

_cache: RouteCache | None = None
def get_route_cache() -> RouteCache:
    global _cache
    if _cache is None:
        _cache = RouteCache()
    return _cache
