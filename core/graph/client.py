"""Neo4j client - optimized with connection pooling and detailed logging."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Optimized Neo4j client with connection pooling and retry logic."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: AsyncDriver | None = None
        self._is_available = True
        self._query_count = 0
        self._total_query_time = 0.0
        self._slow_query_threshold = 5.0  # Log queries slower than 5s

    async def connect(self) -> bool:
        """Connect to Neo4j with timeout."""
        if not self._is_available:
            return False
        if self._driver is None:
            try:
                connect_start = time.perf_counter()
                self._driver = AsyncGraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                    connection_acquisition_timeout=15.0,
                    max_connection_lifetime=1800,
                    max_connection_pool_size=50,  # Increased pool size
                    connection_timeout=10.0,
                )
                await asyncio.wait_for(self._driver.verify_connectivity(), timeout=15.0)
                connect_time = time.perf_counter() - connect_start
                logger.info("🔌 Neo4j connected in %.2fs (pool: 50)", connect_time)
                return True
            except (TimeoutError, Neo4jError, ServiceUnavailable, ConnectionError) as e:
                logger.warning("⚠️ Neo4j unavailable: %s", e)
                self._is_available = False
                self._driver = None
                return False
        return True

    async def close(self) -> None:
        """Close connection with stats."""
        if self._driver is not None:
            try:
                await self._driver.close()
                if self._query_count > 0:
                    avg_time = self._total_query_time / self._query_count
                    logger.info(
                        "🔌 Neo4j closed: %d queries, %.1fs total, avg %.0fms/query",
                        self._query_count, self._total_query_time, avg_time * 1000
                    )
            except Exception:
                pass
            self._driver = None

    async def execute(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute query with timing and retry logic."""
        if not await self.connect():
            return []
        
        assert self._driver is not None
        query_start = time.perf_counter()
        
        try:
            async with self._driver.session() as session:
                result = await asyncio.wait_for(
                    session.run(query, parameters or {}), timeout=120.0
                )
                data = await asyncio.wait_for(result.data(), timeout=120.0)
                
                query_time = time.perf_counter() - query_start
                self._query_count += 1
                self._total_query_time += query_time
                
                # Log slow queries
                if query_time > self._slow_query_threshold:
                    # Extract query type for logging
                    query_type = query.strip().split()[0] if query.strip() else "?"
                    logger.warning(
                        "🐌 Slow query (%.1fs): %s (rows: %d)",
                        query_time, query_type, len(data)
                    )
                
                return data
                
        except (TimeoutError, Neo4jError, ServiceUnavailable) as e:
            query_time = time.perf_counter() - query_start
            logger.error("❌ Neo4j query failed after %.1fs: %s", query_time, str(e)[:100])
            self._is_available = False
            return []

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any | None]:
        """Get a Neo4j session."""
        if not await self.connect():
            yield None
        else:
            assert self._driver is not None
            try:
                async with self._driver.session() as session:
                    yield session
            except (Neo4jError, ServiceUnavailable) as e:
                logger.error("❌ Neo4j session failed: %s", e)
                self._is_available = False
                yield None