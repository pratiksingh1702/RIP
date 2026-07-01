from __future__ import annotations

from pathlib import Path

import pytest

from core.engine import ContextEngine
from core.graph.models import FlowHop, FlowTrace, GraphEdge, GraphNode, SearchResult
from core.parser.base import ParsedEntity, ParsedFile, ParsedRelationship
from core.projects import project_id_for_root
from core.runtime.capabilities import Capability
from core.runtime.doctor import run_doctor
from core.runtime.environment import RuntimeEnvironment, RuntimeMode
from core.runtime.local_indexer import index_local
from core.runtime.resolver import StorageResolver
from core.storage.providers.local_vector_provider import LocalVectorProvider
from core.storage.providers.networkx_provider import NetworkXProvider
from core.storage.providers.sqlite_provider import SQLiteProvider
from core.storage.registry import StorageProvider, StorageRegistry


class FakeProvider:
    name = "fake"
    capabilities = {Capability.GRAPH_TRAVERSAL}

    async def can_initialize(self) -> bool:
        return True

    async def initialize(self):
        return self


class FakeGraph:
    name = "FakeGraph"
    capabilities = {Capability.GRAPH_TRAVERSAL}

    async def trace(self, symbol: str, project_id: str, depth: int = 8):
        return FlowTrace(
            entry_point=symbol,
            hops=[FlowHop(from_symbol=symbol, to_symbol="target", relationship_type="CALLS")],
        )

    async def architecture(self, project_id: str):
        return {
            "services": ["source", "target"],
            "dependencies": [{"source": "source", "target": "target"}],
            "mermaid": 'graph TD\n    "source" --> "target"',
        }

    async def impact(self, symbol: str, project_id: str):
        from core.graph.models import ImpactResult

        return ImpactResult(symbol=symbol, affected_files=["a.py"], risk_level="low")

    async def dependencies(self, target: str, project_id: str):
        return [GraphEdge(source=target, target="dep", relationship_type="IMPORTS")]

    async def find_unused(self, project_id: str, entity_type: str = "all"):
        return [
            GraphNode(
                id="unused",
                label="Function",
                name="unused",
                fqn="unused",
                file_path="a.py",
            )
        ]


class FakeVector:
    name = "FakeVector"
    capabilities = {Capability.VECTOR_SEARCH}

    async def search_similar(self, query: str, project_id: str, limit: int = 20, filters=None):
        return [
            SearchResult(
                entity_id="source",
                entity_type="function",
                name="source",
                file_path="a.py",
                language="Python",
                score=1.0,
                raw_code="def source(): pass",
                project_id=project_id,
            )
        ]


class FakeMetadata:
    name = "FakeMetadata"
    capabilities = {Capability.METADATA_STORAGE}


def _parsed_file(project_id: str | None = None) -> ParsedFile:
    return ParsedFile(
        file_path="a.py",
        language="Python",
        sha256_hash="abc",
        imports=["b.py"],
        project_id=project_id,
        entities=[
            ParsedEntity(
                entity_type="function",
                name="source",
                fqn="source",
                file_path="a.py",
                line_start=1,
                line_end=2,
                language="Python",
                docstring=None,
                decorators=[],
                is_exported=True,
                raw_code="def source(): target()",
                project_id=project_id,
            ),
            ParsedEntity(
                entity_type="function",
                name="target",
                fqn="target",
                file_path="a.py",
                line_start=4,
                line_end=5,
                language="Python",
                docstring=None,
                decorators=[],
                is_exported=True,
                raw_code="def target(): pass",
                project_id=project_id,
            ),
        ],
        relationships=[
            ParsedRelationship(
                from_fqn="source",
                to_fqn="target",
                relationship_type="CALLS",
                file_path="a.py",
                line=2,
                project_id=project_id,
            )
        ],
    )


@pytest.mark.asyncio
async def test_capability_composition_and_registry_order() -> None:
    env = RuntimeEnvironment(
        mode=RuntimeMode.LOCAL,
        graph=FakeGraph(),
        vector=FakeVector(),
        metadata=FakeMetadata(),
        root=Path("."),
        diagnostics=[],
    )
    assert env.has(Capability.GRAPH_TRAVERSAL)
    assert env.has(Capability.VECTOR_SEARCH)
    assert not env.has(Capability.REST_API)

    registry = StorageRegistry()
    low = FakeProvider()
    high = FakeProvider()
    high.name = "high"
    registry.register(StorageProvider(name="low", priority=1, provider_type="graph", factory=low))
    registry.register(
        StorageProvider(name="high", priority=10, provider_type="graph", factory=high)
    )
    resolved = await registry.resolve_first("graph")
    assert resolved.name == "high"


@pytest.mark.asyncio
async def test_local_providers_persist_and_delete_project(tmp_path: Path) -> None:
    project_id = "project-a"
    graph = NetworkXProvider(tmp_path)
    vector = LocalVectorProvider(tmp_path)
    metadata = SQLiteProvider(tmp_path)
    await graph.setup()
    await vector.setup()
    await metadata.setup()

    parsed = _parsed_file(project_id)
    await graph.batch_upsert_files([parsed], project_id)
    await vector.upsert_entities(parsed.entities, project_id)
    await metadata.save_project(tmp_path, project_id=project_id, project_name="Project A")
    await metadata.save_file_hash(project_id, "a.py", "abc")
    await graph.close()
    await vector.close()
    await metadata.close()

    graph = NetworkXProvider(tmp_path)
    vector = LocalVectorProvider(tmp_path)
    metadata = SQLiteProvider(tmp_path)
    await graph.setup()
    await vector.setup()
    await metadata.setup()
    assert (await graph.trace("source", project_id)).hops
    assert await vector.search_similar("source", project_id)
    assert (await metadata.get_project(project_id)).name == "Project A"
    assert await metadata.get_file_hash(project_id, "a.py") == "abc"

    assert await graph.delete_project(project_id) == 2
    assert await vector.delete_project(project_id) == 2
    assert await metadata.delete_project(project_id)
    assert not (await graph.trace("source", project_id)).hops
    assert not await vector.search_similar("source", project_id)
    assert await metadata.get_project(project_id) is None
    await graph.close()
    await vector.close()
    await metadata.close()


@pytest.mark.asyncio
async def test_runtime_resolver_doctor_and_services(tmp_path: Path) -> None:
    env = await StorageResolver(tmp_path, mode="local").resolve()
    try:
        assert env.mode == RuntimeMode.LOCAL
        assert env.description == "NetworkXProvider + LocalVectorProvider + SQLiteProvider"
    finally:
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()

    doctor = await run_doctor(tmp_path, mode="local")
    assert doctor["runtime"]["mode"] == "local"
    assert "GRAPH_TRAVERSAL" in doctor["runtime"]["capabilities"]

    fake_env = RuntimeEnvironment(
        mode=RuntimeMode.LOCAL,
        graph=FakeGraph(),
        vector=FakeVector(),
        metadata=FakeMetadata(),
        root=tmp_path,
        diagnostics=[],
    )
    engine = ContextEngine(fake_env)
    assert await engine.search("source", "p")
    assert (await engine.trace("source", "p")).hops
    assert (await engine.impact("source", "p")).affected_files == ["a.py"]
    assert await engine.dependencies("source", "p")
    assert await engine.dead_code("p")
    assert (await engine.metrics("p"))["source"]["out"] == 1
    assert "Repository Onboarding" in await engine.onboard_markdown("p")


@pytest.mark.asyncio
async def test_provider_aware_local_indexer_with_restart(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def source():\n    return target()\n\ndef target():\n    return 1\n"
    )
    env = await StorageResolver(tmp_path, mode="local").resolve()
    try:
        result = await index_local(tmp_path, env)
        assert result.files_indexed == 1
    finally:
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()

    env = await StorageResolver(tmp_path, mode="local").resolve()
    try:
        project_id = project_id_for_root(tmp_path)
        assert await env.vector.search_similar("source", project_id)
        assert await env.graph.find_unused(project_id)
        projects = await env.metadata.list_projects()
        assert [project.id for project in projects] == [project_id]
    finally:
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()
