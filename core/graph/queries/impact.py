"""Impact Cypher queries."""

from __future__ import annotations

from core.graph.client import Neo4jClient
from core.graph.models import GraphNode, ImpactResult

IMPACT_QUERY = """
MATCH (target {name: $symbol})<-[:CALLS|IMPORTS|DEPENDS_ON*1..5]-(affected)
RETURN affected.name AS name, affected.file_path AS file_path, labels(affected) AS type
"""


async def impact_symbol(client: Neo4jClient, symbol: str) -> ImpactResult:
    records = await client.execute(IMPACT_QUERY, {"symbol": symbol})
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
