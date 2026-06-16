from pathlib import Path

import pytest

from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.queries.impact import impact_symbol
from core.graph.queries.trace import trace_symbol
from core.graph.schema import setup_schema
from core.parser.languages.python import PythonParser

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
FIXTURE = Path("tests/fixtures/sample_repos/python_simple")


async def _client_or_skip() -> Neo4jClient:
    client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        await client.connect()
    except Exception as exc:  # noqa: BLE001 - service may not be running locally
        pytest.skip(f"Neo4j is not available: {exc}")
    return client


@pytest.mark.asyncio
async def test_graph_builder_trace_and_impact_against_neo4j() -> None:
    client = await _client_or_skip()
    try:
        await client.execute("MATCH (n) DETACH DELETE n")
        await setup_schema(client)

        parser = PythonParser()
        builder = GraphBuilder(client)
        parsed_files = []
        for relative in [
            "app.py",
            "services/user_service.py",
            "repositories/user_repository.py",
            "models/user.py",
        ]:
            path = FIXTURE / relative
            parsed_files.append(parser.parse_file(path, path.read_text(encoding="utf-8")))
        stats = await builder.build_from_files(parsed_files)
        assert stats["files"] == len(parsed_files)
        assert stats["entities"] > 0

        functions = await client.execute("MATCH (f:Function) RETURN f.name AS name LIMIT 10")
        assert {record["name"] for record in functions}

        trace = await trace_symbol(client, "get_user")
        assert trace.entry_point == "get_user"

        impact = await impact_symbol(client, "find_user")
        assert impact.symbol == "find_user"
    finally:
        await client.close()
