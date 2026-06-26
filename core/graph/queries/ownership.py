"""Ownership Cypher queries."""

from __future__ import annotations

from collections.abc import Sequence

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


async def create_developers_and_commits_batch(
    client: Neo4jClient,
    rows: Sequence[dict[str, object]],
) -> None:
    """Create Developer/Commit nodes and AUTHORED relationships in one query."""
    if not rows:
        return

    query = """
    UNWIND $rows AS row
    MERGE (d:Developer {email: row.author_email})
    ON CREATE SET d.name = row.author_name
    ON MATCH SET d.name = row.author_name

    MERGE (c:Commit {hash: row.hash})
    SET c.message = row.message,
        c.timestamp = row.timestamp

    MERGE (d)-[:AUTHORED]->(c)
    """
    await client.execute(query, {"rows": list(rows)})


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


async def relate_commits_to_files_batch(
    client: Neo4jClient,
    rows: Sequence[dict[str, object]],
    project_id: str,
) -> None:
    """Create MODIFIES relationships between commits and files in one query."""
    if not rows:
        return

    query = """
    UNWIND $rows AS row
    MATCH (c:Commit {hash: row.hash})
    MERGE (f:File {path: row.file_path, project_id: $project_id})
    MERGE (c)-[:MODIFIES]->(f)
    """
    await client.execute(query, {"rows": list(rows), "project_id": project_id})


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


async def set_file_ownership_batch(
    client: Neo4jClient,
    rows: Sequence[dict[str, object]],
    project_id: str,
) -> None:
    """Create OWNED_BY relationships between files and developers in one query."""
    if not rows:
        return

    query = """
    UNWIND $rows AS row
    MATCH (f:File {path: row.file_path, project_id: $project_id})
    MERGE (d:Developer {email: row.author_email})
    ON CREATE SET d.name = row.author_name
    ON MATCH SET d.name = row.author_name
    MERGE (f)-[r:OWNED_BY]->(d)
    SET r.percentage = row.percentage,
        r.line_count = row.line_count
    """
    await client.execute(query, {"rows": list(rows), "project_id": project_id})
