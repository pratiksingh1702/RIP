"""Qdrant provider wrapper."""

from __future__ import annotations

from core.graph.models import SearchResult
from core.parser.base import ParsedEntity
from core.runtime.capabilities import Capability
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.indexer import SearchIndexer
from core.search.reranker import CrossEncoderReranker
from core.search.searcher import Searcher
from core.storage.database import async_session_factory
from core.storage.interfaces.vector_store import VectorStore
from server.config import get_settings


class QdrantProvider(VectorStore):
    name = "QdrantProvider"
    capabilities = {
        Capability.VECTOR_SEARCH,
        Capability.PERSISTENT_STORAGE,
        Capability.MULTI_PROJECT,
    }

    def __init__(self) -> None:
        settings = get_settings()
        self.client = QdrantClientWrapper(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            vector_size=embedding_dimension(settings.embedding_model),
        )
        self.embedder = EmbeddingPipeline(model_name=settings.embedding_model)
        self.reranker = CrossEncoderReranker()

    async def setup(self) -> None:
        await self.client.init_collection()

    async def upsert_entities(
        self, entities: list[ParsedEntity], project_id: str, project_name: str | None = None
    ) -> int:
        indexer = SearchIndexer(
            self.client,
            self.embedder,
            async_session_factory,
            project_id=project_id,
            project_name=project_name,
        )
        return await indexer.index_entities_batched(entities)

    async def search_similar(
        self,
        query: str,
        project_id: str,
        limit: int = 20,
        filters: dict[str, object] | None = None,
    ) -> list[SearchResult]:
        searcher = Searcher(
            qdrant_client=self.client,
            embedder=self.embedder,
            reranker=self.reranker,
        )
        filters = dict(filters or {})
        filters["project_id"] = project_id
        return await searcher.hybrid_search(
            query=query, filters=filters, top_k=limit, project_id=project_id
        )

    async def delete_project(self, project_id: str) -> int:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        return await self.client.delete(
            Filter(must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))])
        )

    async def close(self) -> None:
        await self.client.close()


async def can_connect_qdrant() -> bool:
    provider = QdrantProvider()
    try:
        await provider.client.count()
        return True
    except Exception:
        return False
    finally:
        await provider.close()
