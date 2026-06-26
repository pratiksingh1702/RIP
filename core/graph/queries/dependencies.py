"""File-level dependency queries."""

from __future__ import annotations

from pathlib import Path

from core.graph.client import Neo4jClient


def _target_params(target: str) -> dict[str, str]:
    normalized = target.replace("\\", "/").strip("/")
    return {
        "target": target,
        "target_norm": normalized,
        "filename": Path(normalized).name or normalized,
    }


async def file_dependencies(
    client: Neo4jClient,
    target: str,
    project_id: str,
    limit: int = 25,
) -> dict:
    """Return file-level incoming/outgoing dependencies and contained symbols."""
    params = {**_target_params(target), "project_id": project_id, "limit": limit}
    matches = await client.execute(
        """
        MATCH (f:File {project_id: $project_id})
        WITH f, replace(f.path, "\\\\", "/") AS normalized
        WHERE toLower(f.path) = toLower($target)
           OR toLower(normalized) = toLower($target_norm)
           OR toLower(normalized) ENDS WITH "/" + toLower($target_norm)
           OR toLower(normalized) ENDS WITH "/" + toLower($filename)
           OR toLower(f.path) ENDS WITH toLower($filename)
        RETURN f.path AS path, f.language AS language
        ORDER BY size(f.path)
        LIMIT 5
        """,
        params,
    )
    if not matches:
        return {
            "target": target,
            "project_id": project_id,
            "matched_file": None,
            "matches": [],
            "imported_by": [],
            "depends_on": [],
            "contains": [],
        }

    file_path = matches[0]["path"]
    query_params = {"file_path": file_path, "project_id": project_id, "limit": limit}

    imported_by = await client.execute(
        """
        MATCH (target:File {path: $file_path, project_id: $project_id})
        OPTIONAL MATCH (target_module:Module {project_id: $project_id})-[:REPRESENTS]->(target)
        WITH target, target_module
        OPTIONAL MATCH (source_file:File {project_id: $project_id})-[:IMPORTS]->(target_module)
        WHERE source_file <> target
        WITH target, target_module, collect(DISTINCT source_file.path) AS direct_paths
        OPTIONAL MATCH (source_module:Module {project_id: $project_id})-[:DEPENDS_ON]->(target_module)
        OPTIONAL MATCH (source_module)-[:REPRESENTS]->(dep_file:File {project_id: $project_id})
        WHERE dep_file <> target
        WITH direct_paths + collect(DISTINCT dep_file.path) AS paths
        UNWIND paths AS path
        WITH DISTINCT path
        WHERE path IS NOT NULL
        RETURN path
        ORDER BY path
        LIMIT $limit
        """,
        query_params,
    )

    depends_on = await client.execute(
        """
        MATCH (source:File {path: $file_path, project_id: $project_id})-[:IMPORTS]->(module:Module)
        OPTIONAL MATCH (module)-[:REPRESENTS]->(dep_file:File {project_id: $project_id})
        WITH DISTINCT
             coalesce(dep_file.path, module.name, module.module_key) AS target,
             dep_file.path IS NULL AS is_external
        WHERE target IS NOT NULL
        RETURN target, is_external
        ORDER BY is_external, target
        LIMIT $limit
        """,
        query_params,
    )

    contains = await client.execute(
        """
        MATCH (:File {path: $file_path, project_id: $project_id})-[:CONTAINS]->(entity)
        RETURN entity.name AS name,
               entity.fqn AS fqn,
               labels(entity) AS labels,
               entity.line_start AS line_start
        ORDER BY coalesce(entity.line_start, 0), entity.name
        LIMIT $limit
        """,
        query_params,
    )

    return {
        "target": target,
        "project_id": project_id,
        "matched_file": matches[0],
        "matches": matches,
        "imported_by": [dict(row) for row in imported_by],
        "depends_on": [dict(row) for row in depends_on],
        "contains": [dict(row) for row in contains],
    }
