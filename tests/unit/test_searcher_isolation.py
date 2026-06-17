"""Searcher project-isolation tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.search.searcher import Searcher


class FakeEmbedder:
    async def embed_texts_async(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeReranker:
    async def rerank_async(self, query, results, top_k=20):
        return results[:top_k]


class FakeQdrant:
    def __init__(self) -> None:
        self.filter = None

    async def query_points(self, query_vector, limit, query_filter=None):
        _ = query_vector, limit
        self.filter = query_filter
        point = SimpleNamespace(
            score=0.9,
            payload={
                "project_id": "project-a",
                "entity_id": "AuthService",
                "entity_type": "class",
                "name": "AuthService",
                "file_path": "auth.py",
                "language": "python",
                "code_preview": "class AuthService: pass",
            },
        )
        return SimpleNamespace(points=[point])


class FakeGraph:
    def __init__(self) -> None:
        self.calls = []

    async def execute(self, query, params=None):
        self.calls.append((query, params or {}))
        if "CONTAINS toLower($query)" in query:
            return []
        if "seed.fqn IN $entity_ids" in query:
            return []
        return [
            {
                "raw_code": "class AuthService: pass",
                "callers": [],
                "callees": [],
            }
        ]


@pytest.mark.asyncio
async def test_hybrid_search_defaults_to_isolated_default_project() -> None:
    qdrant = FakeQdrant()
    searcher = Searcher(qdrant, FakeEmbedder(), FakeReranker(), FakeGraph())

    await searcher.hybrid_search("auth")

    assert any(condition.key == "project_id" for condition in qdrant.filter.must)


@pytest.mark.asyncio
async def test_hybrid_search_applies_project_filter_to_qdrant_and_graph() -> None:
    qdrant = FakeQdrant()
    graph = FakeGraph()
    searcher = Searcher(qdrant, FakeEmbedder(), FakeReranker(), graph)

    results = await searcher.hybrid_search("auth", project_id="project-a")

    assert results[0].project_id == "project-a"
    assert qdrant.filter is not None
    assert any(condition.key == "project_id" for condition in qdrant.filter.must)
    assert all(call[1].get("project_id") == "project-a" for call in graph.calls)
