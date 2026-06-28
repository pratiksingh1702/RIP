"""Architecture Cypher queries."""

from __future__ import annotations

from core.graph.client import Neo4jClient
from core.projects import DEFAULT_PROJECT_ID

ARCHITECTURE_QUERY = """
MATCH (f:File)-[:CONTAINS]->(c:Class)
OPTIONAL MATCH (c)-[:EXTENDS]->(parent:Class)
OPTIONAL MATCH (c)-[:IMPLEMENTS]->(iface:Interface)
OPTIONAL MATCH (c)-[:CONTAINS]->(:Function)-[:CALLS]->(target:Function)
OPTIONAL MATCH (other_class:Class)-[:CONTAINS]->(target)
WHERE (other_class IS NULL OR other_class <> c)
  AND f.project_id = $project_id
  AND c.project_id = $project_id
  AND (parent IS NULL OR parent.project_id = $project_id)
  AND (iface IS NULL OR iface.project_id = $project_id)
  AND (target IS NULL OR target.project_id = $project_id)
  AND (other_class IS NULL OR other_class.project_id = $project_id)
RETURN c.name AS class_name,
       c.file_path AS file_path,
       f.path AS file,
       collect(DISTINCT parent.name) AS extends,
       collect(DISTINCT iface.name) AS implements,
       collect(DISTINCT other_class.name) AS calls_into
ORDER BY class_name
LIMIT 200
"""

ARCHITECTURE_QUERY_WITHOUT_INTERFACES = """
MATCH (f:File)-[:CONTAINS]->(c:Class)
OPTIONAL MATCH (c)-[:EXTENDS]->(parent:Class)
OPTIONAL MATCH (c)-[:CONTAINS]->(:Function)-[:CALLS]->(target:Function)
OPTIONAL MATCH (other_class:Class)-[:CONTAINS]->(target)
WHERE (other_class IS NULL OR other_class <> c)
  AND f.project_id = $project_id
  AND c.project_id = $project_id
  AND (parent IS NULL OR parent.project_id = $project_id)
  AND (target IS NULL OR target.project_id = $project_id)
  AND (other_class IS NULL OR other_class.project_id = $project_id)
RETURN c.name AS class_name,
       c.file_path AS file_path,
       f.path AS file,
       collect(DISTINCT parent.name) AS extends,
       [] AS implements,
       collect(DISTINCT other_class.name) AS calls_into
ORDER BY class_name
LIMIT 200
"""

MODULE_DEPENDENCY_QUERY = """
MATCH (a:Module)-[:DEPENDS_ON]->(b:Module)
WHERE a.project_id = $project_id AND b.project_id = $project_id
RETURN a.name AS source, b.name AS target, 'DEPENDS_ON' AS type
LIMIT 200
"""


async def get_architecture_data(client: Neo4jClient, project_id: str | None = None) -> dict[str, list[dict]]:
    """Query Neo4j for class architecture and module dependencies."""
    project_id = project_id or DEFAULT_PROJECT_ID
    labels = await client.execute("CALL db.labels() YIELD label RETURN collect(label) AS labels")
    rel_types = await client.execute(
        "CALL db.relationshipTypes() YIELD relationshipType "
        "RETURN collect(relationshipType) AS relationship_types"
    )
    known_labels = set(labels[0].get("labels", [])) if labels else set()
    known_rel_types = set(rel_types[0].get("relationship_types", [])) if rel_types else set()
    query = (
        ARCHITECTURE_QUERY
        if "Interface" in known_labels and "IMPLEMENTS" in known_rel_types
        else ARCHITECTURE_QUERY_WITHOUT_INTERFACES
    )
    class_records = await client.execute(query, {"project_id": project_id})
    module_records = await client.execute(MODULE_DEPENDENCY_QUERY, {"project_id": project_id})

    services = [dict(record) for record in class_records]
    dependencies = [dict(record) for record in module_records]
    return {"services": services, "dependencies": dependencies}
