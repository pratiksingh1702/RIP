"""Impact command."""

from __future__ import annotations

import asyncio

from cli.output.formatters import print_json, print_key_values
from core.graph.client import Neo4jClient
from core.graph.queries.impact import impact_symbol
from core.projects import resolve_project_id
from server.config import get_settings


def impact(symbol: str, output_format: str = "text", project: str | None = None) -> None:
    result = asyncio.run(_impact(symbol, project=project))
    if output_format == "json":
        print_json(result.model_dump())
        return
    print_key_values(
        "Impact Analysis",
        {
            "symbol": result.symbol,
            "risk_level": result.risk_level,
            "affected_files": len(result.affected_files),
            "affected_apis": len(result.affected_apis),
        },
    )


async def _impact(symbol: str, project: str | None = None):
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        return await impact_symbol(client, symbol, project_id=resolve_project_id(project))
    finally:
        await client.close()
