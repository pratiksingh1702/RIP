"""Qdrant client."""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams

from core.search.embedder import DEFAULT_MODEL, embedding_dimension

logger = logging.getLogger(__name__)

COLLECTION_NAME = "repo_entities"
VECTOR_SIZE = embedding_dimension(DEFAULT_MODEL)


class QdrantClientWrapper:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        vector_size: int = VECTOR_SIZE,
    ) -> None:
        self.host = host
        self.port = port
        self.vector_size = vector_size
        self._client: AsyncQdrantClient | None = None
        self._is_available = True

    @property
    def client(self) -> AsyncQdrantClient:
        """Expose the underlying async client for diagnostics and tests."""
        if self._client is None:
            self._client = AsyncQdrantClient(host=self.host, port=self.port)
        return self._client

    async def _get_client(self) -> AsyncQdrantClient | None:
        if not self._is_available:
            return None
        if self._client is None:
            try:
                self._client = AsyncQdrantClient(host=self.host, port=self.port)
                # Verify connectivity
                await self._client.get_collections()
                logger.debug("Successfully connected to Qdrant")
            except Exception as e:
                logger.warning(f"Failed to connect to Qdrant: {e}. Disabling vector search.")
                self._is_available = False
                self._client = None
        return self._client

    async def init_collection(self) -> None:
        """Create the collection if it does not exist."""
        client = await self._get_client()
        if client is None:
            logger.warning("Skipping Qdrant collection init because Qdrant is unavailable.")
            return
        try:
            collection = await client.get_collection(COLLECTION_NAME)
            vectors = collection.config.params.vectors
            current_size = getattr(vectors, "size", None)
            logger.info(
                "Qdrant collection %s is ready: vector_size=%s points=%s indexed_vectors=%s",
                COLLECTION_NAME,
                current_size,
                collection.points_count,
                getattr(collection, "indexed_vectors_count", None),
            )
            if current_size is not None and current_size != self.vector_size:
                logger.warning(
                    "Recreating Qdrant collection %s for vector size %s -> %s",
                    COLLECTION_NAME,
                    current_size,
                    self.vector_size,
                )
                await client.delete_collection(COLLECTION_NAME)
                await client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
        except UnexpectedResponse as exc:
            if exc.status_code == 404:
                await client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
                logger.info("Created Qdrant collection %s", COLLECTION_NAME)
            else:
                logger.warning(f"Qdrant init failed: {exc}")
                self._is_available = False
        except Exception as e:
            logger.warning(f"Qdrant init failed: {e}")
            self._is_available = False

    async def upsert(self, points: list[PointStruct]) -> int:
        if not points:
            logger.info("Qdrant upsert skipped: 0 points.")
            return 0
        client = await self._get_client()
        if client is None:
            logger.warning("Qdrant upsert skipped: Qdrant is unavailable.")
            return 0
        try:
            await client.upsert(collection_name=COLLECTION_NAME, points=points)
            logger.info("Qdrant upsert completed: %s points.", len(points))
            return len(points)
        except Exception as e:
            logger.warning(f"Qdrant upsert failed: {e}")
            self._is_available = False
            return 0

    async def search(self, query_vector: list[float], limit: int = 20, **kwargs) -> list[Any]:
        client = await self._get_client()
        if client is None:
            return []
        try:
            return await client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                limit=limit,
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"Qdrant search failed: {e}")
            self._is_available = False
            return []

    async def query_points(self, query_vector: list[float], limit: int = 20, **kwargs) -> Any:
        client = await self._get_client()
        if client is None:
            from types import SimpleNamespace
            logger.warning("Qdrant query skipped: Qdrant is unavailable.")
            return SimpleNamespace(points=[])
        try:
            result = await client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=limit,
                **kwargs,
            )
            logger.info(
                "Qdrant query completed: backend=qdrant limit=%s results=%s",
                limit,
                len(result.points),
            )
            return result
        except Exception as e:
            logger.warning(f"Qdrant query failed: {e}")
            self._is_available = False
            from types import SimpleNamespace
            return SimpleNamespace(points=[])

    async def delete(self, filter_: Any) -> int:
        client = await self._get_client()
        if client is None:
            logger.warning("Qdrant delete skipped: Qdrant is unavailable.")
            return 0
        try:
            matched = await client.count(
                collection_name=COLLECTION_NAME,
                count_filter=filter_,
                exact=True,
            )
            await client.delete(collection_name=COLLECTION_NAME, points_selector=filter_)
            deleted_count = int(matched.count)
            logger.info(
                "Qdrant delete completed for filter: %s matched_points=%s",
                filter_,
                deleted_count,
            )
            return deleted_count
        except Exception as e:
            logger.warning(f"Qdrant delete failed: {e}")
            self._is_available = False
            return 0

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    async def get_points_count(self) -> int:
        """Get the number of points in the collection."""
        client = await self._get_client()
        if client is None:
            return 0
        try:
            collection = await client.get_collection(COLLECTION_NAME)
            return collection.points_count or 0
        except Exception as e:
            logger.warning(f"Failed to get Qdrant points count: {e}")
            return 0
