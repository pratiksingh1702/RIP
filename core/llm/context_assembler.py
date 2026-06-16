"""Token-budgeted context assembly."""

from __future__ import annotations

from core.graph.client import Neo4jClient
from core.graph.models import SearchResult


class ContextAssembler:
    """Assembles codebase context (code, graph relationships, git info, metrics) for LLM prompts."""

    def __init__(self, graph_client: Neo4jClient):
        self.graph_client = graph_client

    async def assemble_context(self, symbol: str, context_level: str = "file") -> dict[str, object]:
        """Assemble context for a given symbol."""
        # 1. Find the target node
        query = """
        MATCH (e)
        WHERE e.fqn = $symbol OR e.name = $symbol
           OR toLower(e.name) CONTAINS toLower($symbol)
           OR toLower(e.fqn) CONTAINS toLower($symbol)
        RETURN e.name AS name, e.fqn AS fqn, e.file_path AS file_path,
               e.raw_code AS raw_code, labels(e)[0] AS type
        LIMIT 1
        """
        records = await self.graph_client.execute(query, {"symbol": symbol})
        if not records:
            return {
                "symbol": symbol,
                "found": False,
                "context_str": f"Symbol '{symbol}' was not found in the codebase graph.",
            }

        target = records[0]
        fqn = target.get("fqn")
        file_path = target.get("file_path")
        raw_code = target.get("raw_code") or ""
        entity_type = target.get("type") or "Unknown"

        # 2. Get incoming callers & outgoing callees
        rel_query = """
        MATCH (e)
        WHERE e.fqn = $fqn
        OPTIONAL MATCH (caller)-[:CALLS]->(e)
        OPTIONAL MATCH (e)-[:CALLS]->(callee)
        RETURN collect(DISTINCT caller.fqn) AS callers,
               collect(DISTINCT callee.fqn) AS callees
        """
        rel_records = await self.graph_client.execute(rel_query, {"fqn": fqn})
        callers = []
        callees = []
        if rel_records:
            callers = rel_records[0].get("callers") or []
            callees = rel_records[0].get("callees") or []

        # 3. Get Git ownership and churn
        git_query = """
        MATCH (f:File)
        WHERE f.path = $file_path OR f.path ENDS WITH $suffix
        OPTIONAL MATCH (f)-[r:OWNED_BY]->(d:Developer)
        OPTIONAL MATCH (c:Commit)-[:MODIFIES]->(f)
        RETURN collect(DISTINCT {name: d.name, percentage: r.percentage}) AS owners,
               count(DISTINCT c) AS churn
        """
        suffix = ""
        if file_path:
            suffix = "/" + file_path.replace("\\", "/").lstrip("/")
        git_records = await self.graph_client.execute(
            git_query,
            {"file_path": file_path, "suffix": suffix},
        )
        owners = []
        churn = 0
        if git_records:
            owners = git_records[0].get("owners") or []
            churn = git_records[0].get("churn", 0)

        # 4. Get coupling metrics
        coupling_query = (
            "MATCH (f:File) "
            "WHERE f.path = $file_path OR f.path ENDS WITH $suffix "
            "MATCH (f)-[:CONTAINS]->(target) "
            "OPTIONAL MATCH (target)<-[:CALLS|IMPORTS|EXTENDS|IMPLEMENTS]-(source)"
            "<-[:CONTAINS]-(f_in:File) "
            "WHERE f_in.path <> f.path "
            "WITH f, count(DISTINCT f_in.path) AS ca "
            "OPTIONAL MATCH (f)-[:CONTAINS]->(source)"
            "-[:CALLS|IMPORTS|EXTENDS|IMPLEMENTS]->(target)"
            "<-[:CONTAINS]-(f_out:File) "
            "WHERE f_out.path <> f.path "
            "RETURN ca AS afferent, count(DISTINCT f_out.path) AS efferent"
        )
        coupling_records = await self.graph_client.execute(
            coupling_query,
            {"file_path": file_path, "suffix": suffix},
        )
        ca = 0
        ce = 0
        if coupling_records:
            ca = coupling_records[0].get("afferent", 0)
            ce = coupling_records[0].get("efferent", 0)

        # 5. Format prompt context
        context_parts = [
            f"Symbol: {symbol} (FQN: {fqn})",
            f"Type: {entity_type}",
            f"File Path: {file_path}",
            "",
            "--- METRICS & GIT HISTORY ---",
            f"Git Churn (Commits): {churn}",
            f"Afferent Coupling (Ca): {ca}",
            f"Efferent Coupling (Ce): {ce}",
            "Git Owners:",
        ]
        for owner in owners:
            if owner.get("name"):
                pct = round(owner.get("percentage", 0) * 100, 1)
                context_parts.append(f"  - {owner['name']}: {pct}%")

        context_parts.extend([
            "",
            "--- RELATIONSHIPS ---",
            f"Callers (depends on this symbol): {', '.join(callers) if callers else 'None'}",
            f"Callees (this symbol calls): {', '.join(callees) if callees else 'None'}",
            "",
            "--- CODE CONTENT ---",
        ])

        # Token budgeting check (rough approximation: 1 token = 4 chars)
        max_chars = 16000  # ~4000 tokens
        if len(raw_code) > max_chars:
            raw_code_truncated = (
                raw_code[:max_chars] + "\n\n... [TRUNCATED DUE TO CONTEXT BUDGET] ..."
            )
            context_parts.append(raw_code_truncated)
        else:
            context_parts.append(raw_code)

        context_str = "\n".join(context_parts)

        return {
            "symbol": symbol,
            "found": True,
            "fqn": fqn,
            "file_path": file_path,
            "entity_type": entity_type,
            "callers": callers,
            "callees": callees,
            "owners": owners,
            "churn": churn,
            "coupling": {"afferent": ca, "efferent": ce},
            "context_str": context_str,
        }

    async def assemble_search_context(
        self,
        topic: str,
        search_results: list[SearchResult],
        max_results: int = 8,
    ) -> dict[str, object]:
        """Assemble explanation context from semantic search plus graph neighbors."""
        if not search_results:
            return {
                "symbol": topic,
                "found": False,
                "context_str": f"No relevant code found for topic: {topic}",
            }

        sections = [f"Topic: {topic}", "", "## Relevant Code Entities"]
        graph_sections: list[str] = []

        for result in search_results[:max_results]:
            sections.extend(
                [
                    "",
                    f"### {result.name} ({result.file_path})",
                    "```",
                    result.raw_code[:1200],
                    "```",
                ]
            )

        for result in search_results[:5]:
            records = await self.graph_client.execute(
                """
                MATCH (n)
                WHERE n.fqn = $entity_id OR n.name = $name
                OPTIONAL MATCH (n)-[out]->(target)
                OPTIONAL MATCH (source)-[inc]->(n)
                RETURN n.name AS name,
                       collect(DISTINCT {rel: type(out), target: target.name}) AS outgoing,
                       collect(DISTINCT {rel: type(inc), source: source.name}) AS incoming
                LIMIT 1
                """,
                {"entity_id": result.entity_id, "name": result.name},
            )
            if not records:
                continue
            record = records[0]
            name = record.get("name") or result.name
            for outgoing in (record.get("outgoing") or [])[:5]:
                target = outgoing.get("target") if outgoing else None
                if target:
                    graph_sections.append(f"- {name} -{outgoing.get('rel')}-> {target}")
            for incoming in (record.get("incoming") or [])[:5]:
                source = incoming.get("source") if incoming else None
                if source:
                    graph_sections.append(f"- {source} -{incoming.get('rel')}-> {name}")

        if graph_sections:
            sections.extend(["", "## Relationships", *graph_sections[:20]])

        context_str = "\n".join(sections)
        return {
            "symbol": topic,
            "found": True,
            "context_str": context_str[:24000],
        }
