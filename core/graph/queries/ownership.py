"""Ownership Cypher queries."""

from __future__ import annotations

from core.graph.client import Neo4jClient


async def create_developer_and_commit(
    client: Neo4jClient,
    commit_hash: str,
    message: str,
    timestamp_str: str,
    author_name: str,
    author_email: str,
) -> None:
    """Create Developer and Commit nodes, and AUTHORED relationship."""
    query = """
    MERGE (d:Developer {email: $author_email})
    ON CREATE SET d.name = $author_name
    ON MATCH SET d.name = $author_name

    MERGE (c:Commit {hash: $commit_hash})
    SET c.message = $message,
        c.timestamp = $timestamp_str

    MERGE (d)-[:AUTHORED]->(c)
    """
    await client.execute(
        query,
        {
            "author_email": author_email,
            "author_name": author_name,
            "commit_hash": commit_hash,
            "message": message,
            "timestamp_str": timestamp_str,
        },
    )


async def relate_commit_to_file(
    client: Neo4jClient,
    commit_hash: str,
    file_path: str,
) -> None:
    """Create MODIFIES relationship between Commit and File nodes."""
    query = """
    MATCH (c:Commit {hash: $commit_hash})
    MATCH (f:File {path: $file_path})
    MERGE (c)-[:MODIFIES]->(f)
    """
    await client.execute(query, {"commit_hash": commit_hash, "file_path": file_path})


async def set_file_ownership(
    client: Neo4jClient,
    file_path: str,
    author_email: str,
    author_name: str,
    percentage: float,
    line_count: int,
) -> None:
    """Create OWNED_BY relationship between File and Developer nodes."""
    query = """
    MERGE (d:Developer {email: $author_email})
    ON CREATE SET d.name = $author_name
    WITH d
    MATCH (f:File {path: $file_path})
    MERGE (f)-[r:OWNED_BY]->(d)
    SET r.percentage = $percentage,
        r.line_count = $line_count
    """
    await client.execute(
        query,
        {
            "file_path": file_path,
            "author_email": author_email,
            "author_name": author_name,
            "percentage": percentage,
            "line_count": line_count,
        },
    )
