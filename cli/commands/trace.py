"""Trace command."""

from __future__ import annotations

import asyncio

from cli.output.formatters import print_json
from core.graph.client import Neo4jClient
from core.graph.queries.trace import trace_symbol
from server.config import get_settings


def trace(
    entry_point: str,
    depth: int = 10,
    output_format: str = "text",
    explain: bool = False,
) -> None:
    _ = depth
    result = asyncio.run(_trace(entry_point, explain=explain))
    if output_format == "json":
        print_json(result.model_dump())
        return
    print(result.mermaid if result.hops else f"No trace found for {entry_point}")
    if result.explanation:
        print("\nExplanation:")
        print(result.explanation)


async def _trace(entry_point: str, explain: bool = False):
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        return await trace_symbol(client, entry_point, explain=explain)
    finally:
        await client.close()
