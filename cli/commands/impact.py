"""Impact command."""

from __future__ import annotations

import asyncio

from cli.output.formatters import print_json, print_key_values
from core.graph.client import Neo4jClient
from core.graph.queries.impact import impact_symbol
from core.projects import resolve_project_id
from server.config import get_settings


def impact(
    symbol: str, output_format: str = "text", project: str | None = None, mode: str = "auto"
) -> None:
    result = asyncio.run(_impact(symbol, project=project, mode=mode))
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


async def _impact(symbol: str, project: str | None = None, mode: str = "auto"):
    if mode in {"local", "auto"}:
        local_result = await _impact_runtime(symbol, project=project, mode=mode)
        if local_result is not None:
            return local_result
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        return await impact_symbol(client, symbol, project_id=resolve_project_id(project))
    finally:
        await client.close()


async def _impact_runtime(symbol: str, project: str | None, mode: str):
    from pathlib import Path

    from core.engine import ContextEngine
    from core.projects import resolve_project_id
    from core.runtime.resolver import StorageResolver

    env = await StorageResolver(Path.cwd(), mode=mode).resolve()
    if mode == "auto" and env.mode.value != "local":
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()
        return None
    try:
        return await ContextEngine(env).impact(symbol, resolve_project_id(project))
    finally:
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()
