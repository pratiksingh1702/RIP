"""Neo4j client."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: AsyncDriver | None = None
        self._is_available = True

    async def connect(self) -> bool:
        if not self._is_available:
            return False
        if self._driver is None:
            try:
                self._driver = AsyncGraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                    connection_acquisition_timeout=30.0,
                    max_connection_lifetime=3600,
                )
                await asyncio.wait_for(self._driver.verify_connectivity(), timeout=30.0)
                logger.debug("Successfully connected to Neo4j")
            except (TimeoutError, Neo4jError, ServiceUnavailable, ConnectionError) as e:
                logger.warning(f"Failed to connect to Neo4j: {e}. Disabling graph operations.")
                self._is_available = False
                self._driver = None
                return False
        return True

    async def close(self) -> None:
        if self._driver is not None:
            try:
                await self._driver.close()
            except Exception:
                pass
            self._driver = None

    async def execute(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not await self.connect():
            return []
        assert self._driver is not None
        try:
            async with self._driver.session() as session:
                result = await asyncio.wait_for(session.run(query, parameters or {}), timeout=300.0)
                return await asyncio.wait_for(result.data(), timeout=300.0)
        except (TimeoutError, Neo4jError, ServiceUnavailable) as e:
            logger.error(f"Neo4j query failed: {e}")
            self._is_available = False
            return []

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any | None]:
        if not await self.connect():
            yield None
        else:
            assert self._driver is not None
            try:
                async with self._driver.session() as session:
                    yield session
            except (Neo4jError, ServiceUnavailable) as e:
                logger.error(f"Neo4j session failed: {e}")
                self._is_available = False
                yield None
