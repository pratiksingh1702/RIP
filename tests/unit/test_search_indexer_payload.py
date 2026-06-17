"""Search indexer payload tests."""

from __future__ import annotations

import pytest

from core.parser.base import ParsedEntity
from core.search.indexer import SearchIndexer


class FakeEmbedder:
    async def embed_entities_async(self, entities: list[ParsedEntity]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in entities]


class FakeQdrant:
    def __init__(self) -> None:
        self.points = []
        self.deletes = []

    async def upsert(self, points):
        self.points.extend(points)
        return len(points)

    async def delete(self, filter_):
        self.deletes.append(filter_)
        return 1


@pytest.mark.asyncio
async def test_qdrant_payload_omits_full_raw_code() -> None:
    qdrant = FakeQdrant()
    entity = ParsedEntity(
        entity_type="function",
        name="build",
        fqn="lib.main.HomePage.build",
        file_path="lib/main.dart",
        line_start=10,
        line_end=20,
        language="dart",
        docstring=None,
        decorators=[],
        is_exported=True,
        raw_code="x" * 2000,
        project_id="project-a",
    )

    inserted = await SearchIndexer(
        qdrant,
        FakeEmbedder(),
        project_id="project-a",
        project_name="app-a",
    ).index_entities([entity])

    assert inserted == 1
    payload = qdrant.points[0].payload
    assert "raw_code" not in payload
    assert payload["code_preview"] == "x" * 500
    assert payload["line_start"] == 10
    assert payload["line_end"] == 20
    assert payload["project_id"] == "project-a"
    assert payload["project_name"] == "app-a"


@pytest.mark.asyncio
async def test_qdrant_delete_requires_project_filter() -> None:
    qdrant = FakeQdrant()
    indexer = SearchIndexer(qdrant, None, project_id="project-a")

    deleted = await indexer.delete_file_embeddings("lib/main.dart")

    assert deleted == 1
    conditions = qdrant.deletes[0].must
    assert {condition.key for condition in conditions} == {"file_path", "project_id"}
