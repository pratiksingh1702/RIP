"""Trace Cypher queries."""

from __future__ import annotations

from core.graph.client import Neo4jClient
from core.graph.models import FlowHop, FlowTrace
from core.llm.client import query_llm
from core.llm.prompts.trace import TRACE_SYSTEM_PROMPT, TRACE_USER_PROMPT
from core.projects import DEFAULT_PROJECT_ID


async def trace_workflow_chain(
    client: Neo4jClient,
    entry_point: str,
    project_id: str | None = None,
    max_hops: int = 8,
) -> tuple[list[dict], str]:
    """Trace a workflow chain from entry point through CALLS+USES+NAVIGATES_TO.
    
    Returns:
        Tuple of (workflow_hops, mermaid_diagram_string)
    """
    query = f"""
    MATCH path = (start {{name: $entry_point, project_id: $project_id}})
        -[:CALLS|USES|NAVIGATES_TO|DEPENDS_ON*1..{max_hops}]->(end)
    WHERE end.project_id = $project_id
    RETURN path
    ORDER BY length(path) DESC
    LIMIT 10
    """
    records = await client.execute(query, {"entry_point": entry_point, "project_id": project_id})
    
    hops = []
    seen_edges = set()
    
    for record in records:
        path = record.get("path")
        if not path:
            continue
        for rel in path.relationships:
            from_name = rel.start_node.get("name") or rel.start_node.get("fqn", "?")
            to_name = rel.end_node.get("name") or rel.end_node.get("fqn", "?")
            rel_type = rel.type
            edge = (from_name, to_name, rel_type)
            if edge not in seen_edges:
                seen_edges.add(edge)
                hops.append({
                    "from": from_name,
                    "to": to_name,
                    "relationship": rel_type,
                    "file_path": rel.get("file_path", ""),
                })
    
    # Generate Mermaid diagram
    mermaid = _workflow_to_mermaid(hops)
    
    return hops, mermaid


def _workflow_to_mermaid(hops: list[dict]) -> str:
    """Convert workflow hops to Mermaid flowchart."""
    lines = ["```mermaid", "graph TD"]
    seen = set()
    for hop in hops[:20]:
        from_n = hop["from"].replace('"', "'")
        to_n = hop["to"].replace('"', "'")
        rel = hop["relationship"]
        edge = f'    {from_n} -->|{rel}| {to_n}'
        if edge not in seen:
            seen.add(edge)
            lines.append(edge)
    lines.append("```")
    return "\n".join(lines)

TRACE_RELATIONSHIP_TYPES = (
    "CALLS",
    "IMPORTS",
    "DEPENDS_ON",
    "EXTENDS",
    "IMPLEMENTS",
    "CONTAINS",
)


def _project_clause(alias: str) -> str:
    return f" AND ({alias}.project_id = $project_id OR $project_id IS NULL)"


def _trace_queries(relationship_pattern: str) -> list[tuple[str, str]]:
    return [
        (
            "any_label_by_name",
            f"""
            MATCH path = (start {{name: $entry_point}})-[:{relationship_pattern}*1..10]->(end)
            WHERE start.project_id = $project_id AND end.project_id = $project_id
            RETURN path
            ORDER BY length(path) DESC
            LIMIT 30
            """,
        ),
        (
            "any_label_by_fqn",
            f"""
            MATCH path = (start {{fqn: $entry_point}})-[:{relationship_pattern}*1..10]->(end)
            WHERE start.project_id = $project_id AND end.project_id = $project_id
            RETURN path
            ORDER BY length(path) DESC
            LIMIT 30
            """,
        ),
        (
            "function_calls",
            """
            MATCH path = (start:Function {name: $entry_point, project_id: $project_id})
                -[:CALLS*1..10]->(end)
            WHERE end.project_id = $project_id
            RETURN path
            ORDER BY length(path) DESC
            LIMIT 30
            """,
        ),
        (
            "class_methods",
            """
            MATCH (cls:Class {name: $entry_point, project_id: $project_id})
                -[:CONTAINS]->(method:Function {project_id: $project_id})
            MATCH path = (method)-[:CALLS*1..8]->(end)
            WHERE end.project_id = $project_id
            RETURN path
            ORDER BY length(path) DESC
            LIMIT 30
            """,
        ),
        (
            "fuzzy",
            f"""
            MATCH (n)
            WHERE n.project_id = $project_id
              AND toLower(n.name) CONTAINS toLower($entry_point)
            MATCH path = (n)-[:{relationship_pattern}*1..6]->(end)
            WHERE end.project_id = $project_id
            RETURN path
            ORDER BY length(path) DESC
            LIMIT 20
            """,
        ),
    ]


async def _available_trace_relationship_pattern(client: Neo4jClient) -> str:
    records = await client.execute(
        "CALL db.relationshipTypes() YIELD relationshipType "
        "RETURN collect(relationshipType) AS relationship_types"
    )
    known = set(records[0].get("relationship_types", [])) if records else set()
    selected = [rel_type for rel_type in TRACE_RELATIONSHIP_TYPES if rel_type in known]
    if not selected:
        selected = ["CALLS"]
    return "|".join(selected)


TRACE_FALLBACK_QUERY = """
MATCH (n)
WHERE n.project_id = $project_id
  AND toLower(n.name) CONTAINS toLower($entry_point)
OPTIONAL MATCH (n)-[r]-(connected)
WHERE connected.project_id = $project_id
RETURN n.name AS from_symbol,
       connected.name AS to_symbol,
       type(r) AS relationship_type,
       coalesce(r.file_path, n.file_path, connected.file_path) AS file_path,
       r.line AS line
LIMIT 20
"""


async def trace_symbol(
    client: Neo4jClient,
    entry_point: str,
    explain: bool = False,
    project_id: str | None = None,
) -> FlowTrace:
    project_id = project_id or DEFAULT_PROJECT_ID
    records = []
    relationship_pattern = await _available_trace_relationship_pattern(client)
    for _strategy, query in _trace_queries(relationship_pattern):
        records = await client.execute(
            query,
            {"entry_point": entry_point, "project_id": project_id},
        )
        if records:
            break

    hops: list[FlowHop] = []

    for record in records:
        path = record.get("path")

        if path is None:
            continue

        relationships = getattr(path, "relationships", [])

        for rel in relationships:
            hops.append(
                FlowHop(
                    from_symbol=(
                        rel.start_node.get("name")
                        or rel.start_node.get("fqn")
                        or ""
                    ),
                    to_symbol=(
                        rel.end_node.get("name")
                        or rel.end_node.get("fqn")
                        or ""
                    ),
                    relationship_type=rel.type,
                    file_path=rel.get("file_path"),
                    line=rel.get("line"),
                )
            )

    if not hops:
        fallback_records = await client.execute(
            TRACE_FALLBACK_QUERY,
            {"entry_point": entry_point, "project_id": project_id},
        )
        for record in fallback_records:
            if not record.get("to_symbol") or not record.get("relationship_type"):
                continue
            hops.append(
                FlowHop(
                    from_symbol=record.get("from_symbol") or entry_point,
                    to_symbol=record.get("to_symbol") or "",
                    relationship_type=record.get("relationship_type") or "RELATED",
                    file_path=record.get("file_path"),
                    line=record.get("line"),
                )
            )

    mermaid_str = _to_mermaid(hops)

    explanation = None

    if explain and hops:
        trace_path = "\n".join(
            f"{h.from_symbol} -> {h.to_symbol} ({h.relationship_type})"
            for h in hops
        )

        prompt = TRACE_USER_PROMPT.format(
            trace_path=trace_path
        )

        explanation = await query_llm(
            prompt,
            system_prompt=TRACE_SYSTEM_PROMPT,
        )

    return FlowTrace(
        entry_point=entry_point,
        hops=hops,
        mermaid=mermaid_str,
        explanation=explanation,
    )


def _to_mermaid(hops: list[FlowHop]) -> str:
    lines = ["graph TD"]

    seen: set[tuple[str, str, str]] = set()

    for hop in hops:
        edge = (
            hop.from_symbol,
            hop.to_symbol,
            hop.relationship_type,
        )

        if edge in seen:
            continue

        seen.add(edge)

        lines.append(
            f'"{hop.from_symbol}" --> "{hop.to_symbol}"'
        )

    return "\n".join(lines)
