"""Long-lived server runtime resources."""

from __future__ import annotations

import time

from core.graph.client import Neo4jClient
from core.runtime.capabilities import SERVER_CAPABILITIES
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.reranker import CrossEncoderReranker
from server.config import Settings


class ServerRuntime:
    """Owns reusable clients and lazy-loaded ML models for `repo serve`."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.started_at = time.time()
        self.neo4j = Neo4jClient(
            settings.neo4j_uri,
            settings.neo4j_user,
            settings.neo4j_password,
        )
        self.qdrant = QdrantClientWrapper(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            vector_size=embedding_dimension(settings.embedding_model),
        )
        self.embedder = EmbeddingPipeline(model_name=settings.embedding_model)
        self.reranker = CrossEncoderReranker()

    async def startup(self) -> None:
        await self.neo4j.connect()
        await self.qdrant.init_collection()

    async def shutdown(self) -> None:
        await self.qdrant.close()
        await self.neo4j.close()

    def status(self) -> dict[str, object]:
        return {
            "uptime_seconds": round(time.time() - self.started_at, 3),
            "embedding_model": self.embedder.model_name,
            "embedding_model_loaded": self.embedder._model is not None,
            "reranker_model": self.reranker.model_name,
            "reranker_model_loaded": self.reranker._model is not None,
            "neo4j_available": self.neo4j._is_available,
            "qdrant_available": self.qdrant._is_available,
            "mode": "server",
            "graph_provider": "Neo4jProvider",
            "vector_provider": "QdrantProvider",
            "metadata_provider": "PostgresProvider",
            "capabilities": sorted(cap.name for cap in SERVER_CAPABILITIES),
        }
