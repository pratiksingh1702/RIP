"""Impact Cypher queries."""

from __future__ import annotations

from core.graph.client import Neo4jClient
from core.graph.models import GraphNode, ImpactResult
from core.projects import DEFAULT_PROJECT_ID

IMPACT_QUERY = """
MATCH (target {name: $symbol, project_id: $project_id})
    <-[:CALLS|IMPORTS|DEPENDS_ON*1..5]-(affected)
WHERE affected.project_id = $project_id
RETURN affected.name AS name, affected.file_path AS file_path, labels(affected) AS type
"""


async def dependency_graph(
    client: Neo4jClient,
    symbol: str,
    project_id: str | None = None,
    direction: str = "both",  # "outgoing", "incoming", "both"
) -> dict[str, list[tuple[str, str]]]:
    """Get dependency graph for a symbol.
    
    Returns:
        {entity_name: [(dependency_name, relationship_type), ...]}
    """
    if direction in ("outgoing", "both"):
        out_query = """
        MATCH (e {name: $symbol, project_id: $project_id})-[r]->(dep)
        WHERE dep.project_id = $project_id
          AND type(r) IN ['CALLS', 'USES', 'DEPENDS_ON', 'EXTENDS', 'IMPLEMENTS', 'NAVIGATES_TO', 'IMPORTS']
        RETURN e.name AS source, dep.name AS target, type(r) AS rel_type
        LIMIT 30
        """
        out_records = await client.execute(out_query, {"symbol": symbol, "project_id": project_id})
    else:
        out_records = []
    
    if direction in ("incoming", "both"):
        in_query = """
        MATCH (dep {project_id: $project_id})-[r]->(e {name: $symbol, project_id: $project_id})
        WHERE type(r) IN ['CALLS', 'USES', 'DEPENDS_ON', 'EXTENDS', 'IMPLEMENTS', 'NAVIGATES_TO', 'IMPORTS']
        RETURN dep.name AS source, e.name AS target, type(r) AS rel_type
        LIMIT 30
        """
        in_records = await client.execute(in_query, {"symbol": symbol, "project_id": project_id})
    else:
        in_records = []
    
    graph = {}
    for r in out_records + in_records:
        source = r.get("source", "")
        target = r.get("target", "")
        rel = r.get("rel_type", "")
        if source and target:
            graph.setdefault(source, []).append((target, rel))
    
    return graph


async def impact_symbol(
    client: Neo4jClient,
    symbol: str,
    project_id: str | None = None,
) -> ImpactResult:
    project_id = project_id or DEFAULT_PROJECT_ID
    records = await client.execute(IMPACT_QUERY, {"symbol": symbol, "project_id": project_id})
    nodes: list[GraphNode] = []
    files: set[str] = set()
    apis: set[str] = set()
    for record in records:
        labels = record.get("type") or []
        label = labels[0] if labels else "Unknown"
        file_path = record.get("file_path")
        if file_path:
            files.add(file_path)
        if "APIRoute" in labels and record.get("name"):
            apis.add(record["name"])
        nodes.append(
            GraphNode(
                id=record.get("name") or "",
                label=label,
                name=record.get("name") or "",
                file_path=file_path,
            )
        )

    risk = "high" if len(files) >= 10 else "medium" if len(files) >= 3 else "low"
    return ImpactResult(
        symbol=symbol,
        affected_files=sorted(files),
        affected_apis=sorted(apis),
        risk_level=risk,
        affected_nodes=nodes,
    )
