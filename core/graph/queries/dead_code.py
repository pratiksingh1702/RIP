"""Dead code Cypher queries."""

from __future__ import annotations

from core.graph.client import Neo4jClient


async def get_dead_functions(client: Neo4jClient, known_entry_points: list[str]) -> list[dict]:
    """Find functions that have no incoming CALLS relationships and are not entry points."""
    query = """
    MATCH (f:Function)
    WHERE NOT ()-[:CALLS]->(f)
      AND NOT f.name IN $known_entry_points
      AND NOT f.fqn IN $known_entry_points
    RETURN f.name AS name, f.file_path AS file_path, f.fqn AS fqn
    """
    records = await client.execute(query, {"known_entry_points": known_entry_points})
    return [dict(r) for r in records]


async def get_dead_classes(client: Neo4jClient) -> list[dict]:
    """Find classes that have no incoming CALLS, EXTENDS, or IMPLEMENTS relationships."""
    query = """
    MATCH (c:Class)
    WHERE NOT ()-[:CALLS|EXTENDS|IMPLEMENTS]->(c)
    RETURN c.name AS name, c.file_path AS file_path, c.fqn AS fqn
    """
    records = await client.execute(query)
    return [dict(r) for r in records]
