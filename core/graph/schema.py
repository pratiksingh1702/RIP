"""Neo4j schema setup."""

from __future__ import annotations

from core.graph.client import Neo4jClient

SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
    (
        "CREATE CONSTRAINT function_fqn_unique IF NOT EXISTS "
        "FOR (fn:Function) REQUIRE fn.fqn IS UNIQUE"
    ),
    "CREATE CONSTRAINT class_fqn_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.fqn IS UNIQUE",
    "CREATE INDEX function_name IF NOT EXISTS FOR (fn:Function) ON (fn.name)",
    "CREATE INDEX file_language IF NOT EXISTS FOR (f:File) ON (f.language)",
]


async def setup_schema(client: Neo4jClient) -> None:
    for statement in SCHEMA_STATEMENTS:
        await client.execute(statement)
