"""Coupling Cypher queries."""

from __future__ import annotations

from core.graph.client import Neo4jClient
from core.projects import DEFAULT_PROJECT_ID


async def get_module_coupling(
    client: Neo4jClient, 
    module_path: str,
    project_id: str | None = None,
) -> dict[str, int]:
    """Calculate afferent and efferent coupling for a given module/file path."""
    project_id = project_id or DEFAULT_PROJECT_ID
    suffix = module_path.replace("\\", "/").lstrip("/")
    if not suffix.startswith("/"):
        suffix = "/" + suffix

    ca_query = """
    MATCH (f:File)
    WHERE (f.path = $module_path OR f.path ENDS WITH $suffix)
      AND f.project_id = $project_id
    MATCH (f)-[:CONTAINS]->(target)
    MATCH (source)-[:CALLS|EXTENDS|IMPLEMENTS]->(target)
    MATCH (f_other:File)-[:CONTAINS]->(source)
    WHERE f_other.path <> f.path
      AND f_other.project_id = $project_id
      AND source.project_id = $project_id
      AND target.project_id = $project_id
    RETURN count(DISTINCT f_other.path) AS afferent_coupling
    """

    ce_query = """
    MATCH (f:File)
    WHERE (f.path = $module_path OR f.path ENDS WITH $suffix)
      AND f.project_id = $project_id
    MATCH (f)-[:CONTAINS]->(source)
    MATCH (source)-[:CALLS|EXTENDS|IMPLEMENTS]->(target)
    MATCH (f_other:File)-[:CONTAINS]->(target)
    WHERE f_other.path <> f.path
      AND f_other.project_id = $project_id
      AND source.project_id = $project_id
      AND target.project_id = $project_id
    RETURN count(DISTINCT f_other.path) AS efferent_coupling
    """

    ca_records = await client.execute(
        ca_query, 
        {"module_path": module_path, "suffix": suffix, "project_id": project_id},
    )
    ce_records = await client.execute(
        ce_query, 
        {"module_path": module_path, "suffix": suffix, "project_id": project_id},
    )

    ca = ca_records[0].get("afferent_coupling", 0) if ca_records else 0
    ce = ce_records[0].get("efferent_coupling", 0) if ce_records else 0

    return {"afferent": ca, "efferent": ce}


async def get_all_coupling(
    client: Neo4jClient,
    project_id: str | None = None,
) -> list[dict]:
    """Calculate coupling metrics for all files in the system."""
    project_id = project_id or DEFAULT_PROJECT_ID
    query = """
    MATCH (f:File)
    WHERE f.project_id = $project_id
    OPTIONAL MATCH (f)-[:CONTAINS]->(target)
    OPTIONAL MATCH (source)-[:CALLS|EXTENDS|IMPLEMENTS]->(target)
    OPTIONAL MATCH (f_in:File)-[:CONTAINS]->(source)
    WHERE (f_in IS NULL OR f_in.path <> f.path)
      AND (f_in IS NULL OR f_in.project_id = $project_id)
      AND (target IS NULL OR target.project_id = $project_id)
      AND (source IS NULL OR source.project_id = $project_id)
    WITH f, count(DISTINCT f_in.path) AS ca
    OPTIONAL MATCH (f)-[:CONTAINS]->(source)
    OPTIONAL MATCH (source)-[:CALLS|EXTENDS|IMPLEMENTS]->(target)
    OPTIONAL MATCH (f_out:File)-[:CONTAINS]->(target)
    WHERE (f_out IS NULL OR f_out.path <> f.path)
      AND (f_out IS NULL OR f_out.project_id = $project_id)
      AND (target IS NULL OR target.project_id = $project_id)
      AND (source IS NULL OR source.project_id = $project_id)
    RETURN f.path AS file_path,
           ca AS afferent,
           count(DISTINCT f_out.path) AS efferent
    """
    records = await client.execute(query, {"project_id": project_id})
    return [dict(record) for record in records]
