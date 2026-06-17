"""Trace command."""

from __future__ import annotations

import asyncio

from cli.output.formatters import print_json
from core.graph.client import Neo4jClient
from core.graph.queries.trace import trace_symbol
from core.projects import resolve_project_id
from server.config import get_settings


def trace(
    entry_point: str,
    depth: int = 10,
    output_format: str = "text",
    explain: bool = False,
    project: str | None = None,
) -> None:
    _ = depth
    result = asyncio.run(_trace(entry_point, explain=explain, project=project))
    if output_format == "json":
        print_json(result.model_dump())
        return
    print(result.mermaid if result.hops else f"No trace found for {entry_point}")
    if result.explanation:
        print("\nExplanation:")
        print(result.explanation)


async def _trace(entry_point: str, explain: bool = False, project: str | None = None):
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        return await trace_symbol(
            client,
            entry_point,
            explain=explain,
            project_id=resolve_project_id(project),
        )
    finally:
        await client.close()
