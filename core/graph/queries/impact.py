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
