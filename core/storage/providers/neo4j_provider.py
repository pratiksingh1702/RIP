"""Neo4j provider wrapper."""

from __future__ import annotations

from core.graph.client import Neo4jClient
from core.graph.models import FlowTrace, GraphEdge, GraphNode, ImpactResult
from core.graph.queries.architecture import get_architecture_data
from core.graph.queries.impact import impact_symbol
from core.graph.queries.trace import trace_symbol
from core.indexer.pipeline import IndexProgress, _write_graph_streaming_fast
from core.parser.base import ParsedFile
from core.runtime.capabilities import Capability
from core.storage.interfaces.graph_store import GraphStore
from server.config import get_settings


class Neo4jProvider(GraphStore):
    name = "Neo4jProvider"
    capabilities = {
        Capability.GRAPH_TRAVERSAL,
        Capability.PERSISTENT_STORAGE,
        Capability.MULTI_PROJECT,
        Capability.CONCURRENT_USERS,
        Capability.SHARED_INDEXES,
    }

    def __init__(self, client: Neo4jClient | None = None) -> None:
        settings = get_settings()
        self.client = client or Neo4jClient(
            settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password
        )

    async def setup(self) -> None:
        await self.client.connect()

    async def batch_upsert_files(self, files: list[ParsedFile], project_id: str) -> dict[str, int]:
        from core.graph.builder import GraphBuilder

        for parsed in files:
            parsed.project_id = project_id
            for entity in parsed.entities:
                entity.project_id = project_id
            for rel in parsed.relationships:
                rel.project_id = project_id

        async def stream():
            for parsed in files:
                yield parsed, None

        builder = GraphBuilder(self.client, project_id=project_id)
        return await _write_graph_streaming_fast(builder, stream(), IndexProgress())

    async def trace(self, symbol: str, project_id: str, depth: int = 8) -> FlowTrace:
        _ = depth
        return await trace_symbol(self.client, symbol, project_id=project_id)

    async def dependencies(self, target: str, project_id: str) -> list[GraphEdge]:
        query = """
        MATCH (n {project_id: $project_id})-[r]->(m {project_id: $project_id})
        WHERE n.name = $target OR n.fqn = $target OR n.file_path = $target
        RETURN coalesce(n.fqn, n.name) AS source,
               coalesce(m.fqn, m.name) AS target,
               type(r) AS relationship_type,
               coalesce(r.file_path, n.file_path) AS file_path,
               r.line AS line
        LIMIT 200
        """
        rows = await self.client.execute(query, {"target": target, "project_id": project_id})
        return [
            GraphEdge(
                source=row.get("source") or "",
                target=row.get("target") or "",
                relationship_type=row.get("relationship_type") or "RELATED",
                properties={"file_path": row.get("file_path"), "line": row.get("line")},
            )
            for row in rows
        ]

    async def architecture(self, project_id: str) -> dict[str, object]:
        data = await get_architecture_data(self.client, project_id=project_id)
        lines = ["graph TD"]
        for row in data.get("dependencies", []):
            source = row.get("source")
            target = row.get("target")
            if source and target:
                lines.append(f'    "{source}" --> "{target}"')
        if len(lines) == 1:
            for row in data.get("services", [])[:50]:
                name = row.get("class_name")
                if name:
                    lines.append(f'    "{name}"')
        data["mermaid"] = "\n".join(lines)
        return data

    async def impact(self, symbol: str, project_id: str) -> ImpactResult:
        return await impact_symbol(self.client, symbol, project_id=project_id)

    async def find_unused(self, project_id: str, entity_type: str = "all") -> list[GraphNode]:
        label_filter = "" if entity_type == "all" else "AND toLower(labels(n)[0]) = toLower($type)"
        query = f"""
        MATCH (n)
        WHERE n.project_id = $project_id {label_filter}
        AND NOT ()-->(n)
        RETURN elementId(n) AS id, labels(n)[0] AS label, n.name AS name, n.fqn AS fqn,
               n.file_path AS file_path, n.language AS language
        LIMIT 200
        """
        rows = await self.client.execute(
            query, {"project_id": project_id, "type": entity_type.rstrip("s")}
        )
        return [
            GraphNode(
                id=row.get("id") or row.get("fqn") or row.get("name") or "",
                label=row.get("label") or "Entity",
                name=row.get("name") or "",
                fqn=row.get("fqn"),
                file_path=row.get("file_path"),
                language=row.get("language"),
            )
            for row in rows
        ]

    async def delete_project(self, project_id: str) -> int:
        rows = await self.client.execute(
            """
            MATCH (n)
            WHERE n.project_id = $project_id
            WITH collect(n) AS nodes
            FOREACH (n IN nodes | DETACH DELETE n)
            RETURN size(nodes) AS deleted
            """,
            {"project_id": project_id},
        )
        return int(rows[0].get("deleted", 0)) if rows else 0

    async def close(self) -> None:
        await self.client.close()


async def can_connect_neo4j(timeout_seconds: float = 1.5) -> bool:
    _ = timeout_seconds
    provider = Neo4jProvider()
    try:
        return bool(await provider.client.connect())
    except Exception:
        return False
    finally:
        await provider.close()
