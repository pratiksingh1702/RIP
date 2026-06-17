"""Searcher for hybrid semantic and structural search."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from qdrant_client.models import FieldCondition, Filter, MatchValue

from core.graph.models import SearchResult
from core.projects import DEFAULT_PROJECT_ID

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
        project_id: str | None = None,
    ) -> list[SearchResult]:
        """Perform project-scoped BM25 + vector + graph expansion search."""
        project_id = (
            project_id
            or (filters or {}).get("project_id")
            or await self._single_indexed_project_id()
            or DEFAULT_PROJECT_ID
        )

        query_vectors = await self.embedder.embed_texts_async([query])
        query_vector = query_vectors[0]

        filters = {**(filters or {}), "project_id": project_id}
        qdrant_filter = self._build_filter(filters)

        limit = max(top_k * 3, 30)
        logger.info(
            "Search backend selected: hybrid query=%r top_k=%s filters=%s",
            query,
            top_k,
            filters,
        )
        qdrant_response = await self.qdrant_client.query_points(
            query_vector=query_vector,
            limit=limit,
            query_filter=qdrant_filter,
        )

        candidates: dict[str, SearchResult] = {}
        for point in qdrant_response.points:
            payload = point.payload or {}
            self._merge_candidate(
                candidates,
                SearchResult(
                    entity_id=str(payload.get("entity_id", "")),
                    entity_type=str(payload.get("entity_type", "")),
                    name=str(payload.get("name", "")),
                    file_path=str(payload.get("file_path", "")),
                    language=str(payload.get("language", "")),
                    score=float(point.score),
                    raw_code=str(payload.get("code_preview", "")),
                    project_id=str(payload.get("project_id") or project_id),
                ),
            )
        logger.info("Qdrant semantic search returned %s raw results.", len(qdrant_response.points))

        for result in await self._bm25_candidates(query, project_id, limit=30):
            self._merge_candidate(candidates, result)

        seed_ids = list(candidates.keys())[:50]
        for result in await self._graph_neighbors(seed_ids, project_id, limit=50):
            self._merge_candidate(candidates, result)

        results = list(candidates.values())[:100]
        for result in results:
            await self._enrich_result(result, project_id)

        reranked = await self.reranker.rerank_async(query, results, top_k=top_k)
        return reranked

    def _merge_candidate(
        self,
        candidates: dict[str, SearchResult],
        result: SearchResult,
    ) -> None:
        if not result.entity_id:
            return
        existing = candidates.get(result.entity_id)
        if existing is None or result.score > existing.score:
            candidates[result.entity_id] = result
        elif result.raw_code and not existing.raw_code:
            existing.raw_code = result.raw_code

    async def _single_indexed_project_id(self) -> str | None:
        records = await self.graph_client.execute(
            "MATCH (p:Project) RETURN collect(p.id) AS project_ids LIMIT 1"
        )
        project_ids = records[0].get("project_ids", []) if records else []
        project_ids = [project_id for project_id in project_ids if project_id]
        return project_ids[0] if len(project_ids) == 1 else None

    async def _bm25_candidates(
        self,
        query: str,
        project_id: str,
        limit: int,
    ) -> list[SearchResult]:
        records = await self.graph_client.execute(
            """
            MATCH (e)
            WHERE e.project_id = $project_id
              AND (e.fqn IS NOT NULL OR e.name IS NOT NULL)
              AND (
                toLower(coalesce(e.name, "")) CONTAINS toLower($query)
                OR toLower(coalesce(e.fqn, "")) CONTAINS toLower($query)
                OR toLower(coalesce(e.raw_code, "")) CONTAINS toLower($query)
                OR toLower(coalesce(e.docstring, "")) CONTAINS toLower($query)
              )
            RETURN e.fqn AS entity_id,
                   labels(e)[0] AS entity_type,
                   e.name AS name,
                   e.file_path AS file_path,
                   e.language AS language,
                   e.raw_code AS raw_code,
                   e.project_id AS project_id
            LIMIT $limit
            """,
            {"query": query, "project_id": project_id, "limit": limit},
        )
        return [
            SearchResult(
                entity_id=record.get("entity_id") or record.get("name") or "",
                entity_type=record.get("entity_type") or "",
                name=record.get("name") or "",
                file_path=record.get("file_path") or "",
                language=record.get("language") or "",
                score=0.65,
                raw_code=(record.get("raw_code") or "")[:1200],
                project_id=record.get("project_id") or project_id,
            )
            for record in records
        ]

    async def _graph_neighbors(
        self,
        entity_ids: list[str],
        project_id: str,
        limit: int,
    ) -> list[SearchResult]:
        if not entity_ids:
            return []
        records = await self.graph_client.execute(
            """
            MATCH (seed)
            WHERE seed.project_id = $project_id AND seed.fqn IN $entity_ids
            MATCH (seed)-[:CALLS|IMPORTS|DEPENDS_ON|EXTENDS|IMPLEMENTS|CONTAINS*1..2]-(n)
            WHERE n.project_id = $project_id AND (n.fqn IS NOT NULL OR n.name IS NOT NULL)
            RETURN DISTINCT n.fqn AS entity_id,
                   labels(n)[0] AS entity_type,
                   n.name AS name,
                   n.file_path AS file_path,
                   n.language AS language,
                   n.raw_code AS raw_code,
                   n.project_id AS project_id
            LIMIT $limit
            """,
            {"entity_ids": entity_ids, "project_id": project_id, "limit": limit},
        )
        return [
            SearchResult(
                entity_id=record.get("entity_id") or record.get("name") or "",
                entity_type=record.get("entity_type") or "",
                name=record.get("name") or "",
                file_path=record.get("file_path") or "",
                language=record.get("language") or "",
                score=0.45,
                raw_code=(record.get("raw_code") or "")[:1200],
                project_id=record.get("project_id") or project_id,
            )
            for record in records
        ]

    async def _enrich_result(self, result: SearchResult, project_id: str) -> None:
        records = await self.graph_client.execute(
            """
            MATCH (e {fqn: $fqn, project_id: $project_id})
            OPTIONAL MATCH (caller {project_id: $project_id})-[:CALLS]->(e)
            OPTIONAL MATCH (e)-[:CALLS]->(callee {project_id: $project_id})
            RETURN e.raw_code AS raw_code,
                   collect(DISTINCT caller.name) AS callers,
                   collect(DISTINCT callee.name) AS callees
            """,
            {"fqn": result.entity_id, "project_id": project_id},
        )
        if records:
            result.raw_code = (records[0].get("raw_code") or result.raw_code or "")[:1200]
            result.callers = [name for name in records[0].get("callers", []) if name]
            result.callees = [name for name in records[0].get("callees", []) if name]

    def _build_filter(self, filters: dict[str, str | None] | None) -> Filter | None:
        if not filters:
            return None

        conditions = []
        for key, val in filters.items():
            if val is not None and val != "":
                conditions.append(FieldCondition(key=key, match=MatchValue(value=val)))

        return Filter(must=conditions) if conditions else None
