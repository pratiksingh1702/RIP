from pathlib import Path

import pytest

from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.schema import setup_schema
from core.llm.client import query_llm
from core.llm.context_assembler import ContextAssembler
from core.parser.languages.python import PythonParser

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
FIXTURE = Path("tests/fixtures/sample_repos/python_simple")


async def _client_or_skip() -> Neo4jClient:
    client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        await client.connect()
    except Exception as exc:
        pytest.skip(f"Neo4j is not available: {exc}")
    return client


@pytest.mark.asyncio
async def test_llm_context_assembly_and_query() -> None:
    client = await _client_or_skip()
    try:
        await client.execute("MATCH (n) DETACH DELETE n")
        await setup_schema(client)

        parser = PythonParser()
        builder = GraphBuilder(client)
        path = FIXTURE / "app.py"
        parsed = parser.parse_file(path, path.read_text(encoding="utf-8"))
        await builder.build_from_file(parsed)

        assembler = ContextAssembler(client)
        context_data = await assembler.assemble_context("get_user", "file")
        assert context_data.get("found") is True
        assert "get_user" in context_data["context_str"]

        resp = await query_llm("test prompt")
        assert len(resp) > 0
    finally:
        await client.close()
