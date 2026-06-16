"""Searcher for hybrid semantic and structural search."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from qdrant_client.models import FieldCondition, Filter, MatchValue

from core.graph.models import SearchResult

if TYPE_CHECKING:
    from core.graph.client import Neo4jClient
    from core.search.client import QdrantClientWrapper
    from core.search.embedder import EmbeddingPipeline
    from core.search.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)


class Searcher:
    def __init__(
        self,
        qdrant_client: QdrantClientWrapper,
        embedder: EmbeddingPipeline,
        reranker: CrossEncoderReranker,
        graph_client: Neo4jClient,
    ) -> None:
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.reranker = reranker
        self.graph_client = graph_client

    async def hybrid_search(
        self,
        query: str,
        filters: dict[str, str | None] | None = None,
        top_k: int = 20,
    ) -> list[SearchResult]:
        """Perform hybrid search: vector query, payload filtering,
        graph enrichment, and reranking.
        """
        # 1. Embed query
        query_vectors = await self.embedder.embed_texts_async([query])
        query_vector = query_vectors[0]

        # Build metadata filters
        qdrant_filter = self._build_filter(filters)

        limit = top_k * 2
        logger.info(
            "Search backend selected: qdrant_semantic query=%r top_k=%s filters=%s",
            query,
            top_k,
            filters or {},
        )
        qdrant_results = await self.qdrant_client.query_points(
            query_vector=query_vector,
            limit=limit,
            query_filter=qdrant_filter,
        )

        results = []
        for point in qdrant_results.points:
            payload = point.payload or {}
            results.append(
                SearchResult(
                    entity_id=payload.get("entity_id", ""),
                    entity_type=payload.get("entity_type", ""),
                    name=payload.get("name", ""),
                    file_path=payload.get("file_path", ""),
                    language=payload.get("language", ""),
                    score=point.score,
                    raw_code=payload.get("raw_code", ""),
                )
            )
        logger.info("Qdrant semantic search returned %s raw results.", len(results))

        # 3. Enrich with graph context from Neo4j
        if results:
            for r in results:
                # Query callers and callees for this FQN
                records = await self.graph_client.execute(
                    """
                    MATCH (e {fqn: $fqn})
                    OPTIONAL MATCH (caller)-[:CALLS]->(e)
                    OPTIONAL MATCH (e)-[:CALLS]->(callee)
                    RETURN collect(DISTINCT caller.name) AS callers,
                           collect(DISTINCT callee.name) AS callees
                    """,
                    {"fqn": r.entity_id},
                )
                if records:
                    r.callers = [name for name in records[0].get("callers", []) if name]
                    r.callees = [name for name in records[0].get("callees", []) if name]

        # 4. Rerank using cross-encoder
        reranked = await self.reranker.rerank_async(query, results, top_k=top_k)
        return reranked

    def _build_filter(self, filters: dict[str, str | None] | None) -> Filter | None:
        if not filters:
            return None

        conditions = []
        for key, val in filters.items():
            if val is not None and val != "":
                conditions.append(FieldCondition(key=key, match=MatchValue(value=val)))

        return Filter(must=conditions) if conditions else None
