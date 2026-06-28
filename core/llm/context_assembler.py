"""Architecture-aware context assembly for explain."""

from __future__ import annotations

from core.graph.client import Neo4jClient
from core.graph.models import SearchResult
from core.llm.models import ExplainContext, ExplainIntent
from core.projects import DEFAULT_PROJECT_ID


class ContextAssembler:
    """Assembles architectural context (workflow, dependencies, state, API) for LLM prompts."""

    def __init__(self, graph_client: Neo4jClient, project_id: str | None = None):
        self.graph_client = graph_client
        self.project_id = project_id or DEFAULT_PROJECT_ID

    # ========================================================================
    # INTENT DETECTION
    # ========================================================================
    
    def detect_intent(self, query: str) -> ExplainIntent:
        """Detect what kind of explanation the user wants - language agnostic."""
        q = query.lower()
        
        # Flow detection - "how X works", workflow, process
        flow_keywords = [
            "how", "work", "flow", "process", "workflow", "steps", "pipeline",
            "journey", "lifecycle", "sequence", "chain", "path", "route"
        ]
        if any(kw in q for kw in flow_keywords):
            return ExplainIntent.FLOW
        
        # Architecture detection - structure, modules, design
        arch_keywords = [
            "architecture", "structure", "modules", "overview", "design",
            "pattern", "organization", "layout", "system", "component"
        ]
        if any(kw in q for kw in arch_keywords):
            return ExplainIntent.ARCHITECTURE
        
        # API detection - endpoints, HTTP, routes, services
        api_keywords = [
            "api", "endpoint", "request", "response", "http", "rest", "graphql",
            "rpc", "route", "controller", "handler", "middleware", "service"
        ]
        if any(kw in q for kw in api_keywords):
            return ExplainIntent.API
        
        # State detection - state, data, store, cache
        state_keywords = [
            "state", "data", "store", "cache", "session", "storage",
            "database", "persistence", "model", "entity", "record"
        ]
        if any(kw in q for kw in state_keywords):
            return ExplainIntent.STATE
        
        # Dependency detection - depends, uses, calls, imports
        dep_keywords = [
            "depend", "dependenc", "import", "call", "use", "coupling",
            "impact", "affect", "related", "connect"
        ]
        if any(kw in q for kw in dep_keywords):
            return ExplainIntent.DEPENDENCY
        
        return ExplainIntent.SEMANTIC

    # ========================================================================
    # MAIN ENTRY POINT
    # ========================================================================
    
    async def assemble_context(
        self,
        symbol: str,
        context_level: str = "file",
        search_results: list[SearchResult] | None = None,
    ) -> ExplainContext:
        """Assemble full architectural context for explanation."""
        intent = self.detect_intent(symbol)
        ctx = ExplainContext(query=symbol, intent=intent)
        
        # Find primary entity - prefer search results over exact symbol lookup
        entity = None
        
        # First: try to get the top search result as primary entity
        if search_results:
            top_result = search_results[0]
            # Try FQN first (more specific), then name
            entity = await self._find_entity(top_result.entity_id)  # FQN from search
            if not entity:
                entity = await self._find_entity(top_result.name)  # Name from search
        
        # Second: try exact symbol lookup (for cases like "typeProvider" not "How typeProvider works")
        if not entity:
            entity = await self._find_entity(symbol)
        
        # Third: try fuzzy lookup with individual words from query
        if not entity:
            words = symbol.split()
            for word in words:
                if len(word) > 3 and word.lower() not in ("how", "what", "why", "does", "work", "explain"):
                    entity = await self._find_entity(word)
                    if entity:
                        break
        
        if not entity:
            # Still have search results - use them for context
            if search_results:
                ctx.found = True
                ctx.important_entities = [
                    {"name": r.name, "type": r.entity_type, "file_path": r.file_path}
                    for r in search_results[:10]
                ]
                ctx.overview = f"Found {len(search_results)} relevant components for '{symbol}'."
                ctx.context_str = self._format_search_context(symbol, search_results)
                return ctx
            
            ctx.context_str = f"Symbol '{symbol}' was not found in the codebase graph."
            return ctx
        
        ctx.found = True
        ctx.important_entities = [entity]
        feature = entity.get("feature_module")
        ctx.feature = feature
        
        # Build context based on intent
        if intent == ExplainIntent.FLOW:
            await self._build_flow_context(ctx, entity, search_results)
        elif intent == ExplainIntent.ARCHITECTURE:
            await self._build_architecture_context(ctx, entity)
        elif intent == ExplainIntent.API:
            await self._build_api_context(ctx, entity)
        elif intent == ExplainIntent.STATE:
            await self._build_state_context(ctx, entity)
        else:
            await self._build_semantic_context(ctx, entity, search_results)
        
        # Generate context string
        ctx.context_str = self._format_context(ctx)
        ctx.suggestions = self._generate_suggestions(ctx)
        
        return ctx
    
    def _format_search_context(self, query: str, search_results: list[SearchResult]) -> str:
        """Format search results when no primary entity is found."""
        parts = [
            f"## EXPLANATION: {query}",
            "",
            f"### SEARCH RESULTS ({len(search_results)} found)",
            "",
        ]
        for r in search_results[:10]:
            parts.append(f"- **{r.name}** ({r.entity_type}) — `{r.file_path}`")
            if r.raw_code:
                parts.append(f"  ```\n  {r.raw_code[:200]}...\n  ```")
        return "\n".join(parts)
    
    async def assemble_search_context(self, topic: str, search_results: list[SearchResult]) -> dict:
        """Legacy method - now delegates to assemble_context."""
        ctx = await self.assemble_context(topic, search_results=search_results)
        return {
            "symbol": topic,
            "found": ctx.found,
            "context_str": ctx.context_str,
        }

    # ========================================================================
    # ENTITY FINDER
    # ========================================================================
    
    async def _find_entity(self, symbol: str) -> dict | None:
        """Find an entity by name, FQN, or partial match."""
        # Try exact name match first
        query = """
        MATCH (e)
        WHERE e.project_id = $project_id
          AND (e.name = $symbol OR e.fqn = $symbol)
        OPTIONAL MATCH (f:File {project_id: $project_id})-[:CONTAINS]->(e)
        RETURN e.name AS name, e.fqn AS fqn, e.file_path AS file_path,
               e.raw_code AS raw_code, labels(e) AS labels,
               e.line_start AS line_start, e.line_end AS line_end,
               f.path AS module_path
        LIMIT 1
        """
        records = await self.graph_client.execute(query, {"symbol": symbol, "project_id": self.project_id})
        if records:
            r = records[0]
            labels = r.get("labels", ["Unknown"])
            return {
                "name": r.get("name", ""),
                "fqn": r.get("fqn", ""),
                "file_path": r.get("file_path", ""),
                "raw_code": r.get("raw_code", ""),
                "type": labels[0] if labels else "Unknown",
                "line_start": r.get("line_start", 1),
                "line_end": r.get("line_end", 1),
            }
        
        # Try partial match on name (for cases like "typeProvider" matching "type_provider")
        query2 = """
        MATCH (e)
        WHERE e.project_id = $project_id
          AND (toLower(e.name) CONTAINS toLower($symbol)
               OR toLower(e.fqn) CONTAINS toLower($symbol))
        OPTIONAL MATCH (f:File {project_id: $project_id})-[:CONTAINS]->(e)
        RETURN e.name AS name, e.fqn AS fqn, e.file_path AS file_path,
               e.raw_code AS raw_code, labels(e) AS labels,
               e.line_start AS line_start, e.line_end AS line_end,
               f.path AS module_path
        LIMIT 1
        """
        records2 = await self.graph_client.execute(query2, {"symbol": symbol, "project_id": self.project_id})
        if records2:
            r = records2[0]
            labels = r.get("labels", ["Unknown"])
            return {
                "name": r.get("name", ""),
                "fqn": r.get("fqn", ""),
                "file_path": r.get("file_path", ""),
                "raw_code": r.get("raw_code", ""),
                "type": labels[0] if labels else "Unknown",
                "line_start": r.get("line_start", 1),
                "line_end": r.get("line_end", 1),
            }
        
        return None

    # ========================================================================
    # FLOW CONTEXT - "How X works"
    # ========================================================================
    
    async def _build_flow_context(self, ctx: ExplainContext, entity: dict, search_results=None):
        """Build workflow chain from entity - handles Module vs Function/Class differently."""
        fqn = entity.get("fqn", "")
        name = entity.get("name", "")
        etype = entity.get("type", "")
        
        # If this is a Module, find the Functions/Classes inside it first
        if etype == "Module":
            # Find what's CONTAINED within this module
            contained_query = """
            MATCH (f:File {project_id: $project_id})-[:CONTAINS]->(m:Module {fqn: $fqn, project_id: $project_id})
            MATCH (f)-[:CONTAINS]->(entity)
            WHERE entity.project_id = $project_id
              AND (entity:Function OR entity:Class OR entity:Widget)
            RETURN entity.name AS name, entity.fqn AS fqn, labels(entity) AS labels
            LIMIT 30
            """
            contained = await self.graph_client.execute(
                contained_query, {"fqn": fqn, "project_id": self.project_id}
            )
            
            ctx.important_entities = []
            for r in contained:
                labels_list = r.get("labels", ["Unknown"])
                ctx.important_entities.append({
                    "name": r.get("name", ""),
                    "type": labels_list[0] if labels_list else "Unknown",
                    "fqn": r.get("fqn", ""),
                })
            
            # If nothing found in module, try finding by partial name match
            if not ctx.important_entities:
                ctx.important_entities = [entity]
            
            all_workflow = []
            all_deps = {}
            
            for ent in ctx.important_entities[:5]:
                ent_name = ent.get("name", "")
                ent_fqn = ent.get("fqn", ent_name)
                
                # Get direct CALLS from this entity
                dep_query = """
                MATCH (e {fqn: $fqn, project_id: $project_id})-[r:CALLS]->(dep)
                WHERE dep.project_id = $project_id
                RETURN dep.name AS name, type(r) AS rel_type, labels(dep) AS dep_labels, dep.fqn AS dep_fqn
                LIMIT 15
                """
                deps = await self.graph_client.execute(
                    dep_query, {"fqn": ent_fqn, "project_id": self.project_id}
                )
                
                for r in deps:
                    dep_name = r.get("name", "")
                    rel = r.get("rel_type", "")
                    labels_list = r.get("dep_labels", ["Unknown"])
                    dep_type = labels_list[0] if labels_list else "Unknown"
                    dep_fqn = r.get("dep_fqn", "")
                    
                    all_deps.setdefault(ent_name, []).append((dep_type, rel, dep_name))
                    
                    all_workflow.append({
                        "from": ent_name,
                        "to": dep_name,
                        "relationship": rel,
                        "type": dep_type,
                        "fqn": dep_fqn,
                    })
                    
                    # Second-level: what does this dep call?
                    dep_dep_query = """
                    MATCH (e {fqn: $fqn, project_id: $project_id})-[r:CALLS]->(dep2)
                    WHERE dep2.project_id = $project_id
                    RETURN dep2.name AS name, type(r) AS rel_type, labels(dep2) AS dep_labels
                    LIMIT 10
                    """
                    dep_deps = await self.graph_client.execute(
                        dep_dep_query, {"fqn": dep_fqn, "project_id": self.project_id}
                    )
                    
                    for dr in dep_deps:
                        dd_name = dr.get("name", "")
                        dd_rel = dr.get("rel_type", "")
                        dd_labels = dr.get("dep_labels", ["Unknown"])
                        dd_type = dd_labels[0] if dd_labels else "Unknown"
                        
                        all_workflow.append({
                            "from": dep_name,
                            "to": dd_name,
                            "relationship": dd_rel,
                            "type": dd_type,
                            "fqn": "",
                        })
                        all_deps.setdefault(dep_name, []).append((dd_type, dd_rel, dd_name))
            
            ctx.workflow_chain = all_workflow
            ctx.dependency_graph = {
                k: [(n, r) for t, r, n in v[:5]] for k, v in all_deps.items()
            }
            
            # Count imports - try multiple patterns
            import_query = """
            MATCH (other:File {project_id: $project_id})-[r:IMPORTS]->(m)
            WHERE m.project_id = $project_id
              AND (m.fqn = $fqn
                OR m.fqn CONTAINS $short_name
                OR m.name CONTAINS $short_name)
            RETURN count(other) AS import_count
            """
            # Handle Windows paths (using backslash) and extract the short name
            short_name = name.split("\\")[-1].split("/")[-1].replace(".dart", "")
            import_result = await self.graph_client.execute(
                import_query, {"fqn": fqn, "short_name": short_name, "project_id": self.project_id}
            )
            import_ct = import_result[0].get("import_count", 0) if import_result else 0
            
            # Calculate total calls (handles both 2-item and 3-item tuples in all_deps)
            total_calls = 0
            for v in all_deps.values():
                for item in v:
                    # item can be (dep_type, rel_type) or (dep_type, rel_type, dep_name)
                    rel = item[1] if len(item) >= 2 else ""
                    if rel == "CALLS":
                        total_calls += 1
            
            entity_names = [e['name'] for e in ctx.important_entities[:5]]
            
            ctx.overview = (
                f"`{name}` is imported by **{import_ct} files** and contains "
                f"**{len(ctx.important_entities)} components** "
                f"({', '.join(entity_names) if entity_names else 'none found'}) "
                f"with **{total_calls} CALLS relationships**."
            )
            
            # Get important files
            file_query = """
            MATCH (f:File {project_id: $project_id})-[:CONTAINS]->(m {fqn: $fqn, project_id: $project_id})
            RETURN f.path AS file_path
            """
            file_result = await self.graph_client.execute(
                file_query, {"fqn": fqn, "project_id": self.project_id}
            )
            ctx.important_files = [r.get("file_path", "") for r in file_result if r.get("file_path")]
            
        else:
            # Non-Module entity: trace CALLS directly
            dep_query = """
            MATCH (e {fqn: $fqn, project_id: $project_id})-[r:CALLS|DEPENDS_ON]->(dep)
            WHERE dep.project_id = $project_id
            RETURN dep.name AS name, type(r) AS rel_type, labels(dep) AS dep_labels
            LIMIT 20
            """
            deps = await self.graph_client.execute(
                dep_query, {"fqn": fqn, "project_id": self.project_id}
            )
            
            ctx.dependency_graph = {}
            ctx.workflow_chain = []
            
            for r in deps:
                dep_name = r.get("name", "")
                rel = r.get("rel_type", "")
                labels_list = r.get("dep_labels", ["Unknown"])
                dep_type = labels_list[0] if labels_list else "Unknown"
                ctx.dependency_graph.setdefault(name, []).append((dep_name, rel))
                ctx.workflow_chain.append({
                    "from": name,
                    "to": dep_name,
                    "relationship": rel,
                    "type": dep_type,
                })
            
            total_deps = len(deps)
            ctx.overview = (
                f"`{name}` ({etype}) has **{total_deps} direct dependencies** "
                f"through CALLS and DEPENDS_ON relationships."
            )
    # ========================================================================
    # ARCHITECTURE CONTEXT
    # ========================================================================
    
    async def _build_architecture_context(self, ctx: ExplainContext, entity: dict):
        """Build module/feature architecture overview."""
        feature = ctx.feature or entity.get("name")
        
        query = """
        MATCH (e {project_id: $project_id})
        WHERE e.name CONTAINS $feature
        OPTIONAL MATCH (e)-[r]->(dep {project_id: $project_id})
        WHERE type(r) IN ['CALLS', 'DEPENDS_ON', 'EXTENDS', 'IMPLEMENTS', 'CONTAINS', 'IMPORTS']
        RETURN e.name AS name, labels(e)[0] AS type, e.file_path AS file_path,
               collect(DISTINCT {dep: dep.name, rel: type(r)}) AS deps
        LIMIT 30
        """
        records = await self.graph_client.execute(query, {"feature": feature, "project_id": self.project_id})
        
        ctx.important_entities = [{
            "name": r.get("name", ""),
            "type": r.get("type", ""),
            "file_path": r.get("file_path", ""),
        } for r in records]
        
        ctx.overview = f"Feature `{feature}` contains {len(ctx.important_entities)} architectural components."

    # ========================================================================
    # API CONTEXT
    # ========================================================================
    
    async def _build_api_context(self, ctx: ExplainContext, entity: dict):
        """Build API flow chain."""
        fqn = entity.get("fqn")
        
        query = """
        MATCH path = (start {fqn: $fqn, project_id: $project_id})
            -[:CALLS|DEPENDS_ON|IMPORTS*1..5]->(dep {project_id: $project_id})
        RETURN dep.name AS name, labels(dep)[0] AS type
        LIMIT 10
        """
        records = await self.graph_client.execute(query, {"fqn": fqn, "project_id": self.project_id})
        
        for r in records:
            name = r.get("name", "")
            if name:
                ctx.api_endpoints.append({"endpoint": name})
        
        ctx.overview = f"API flow from `{entity.get('name')}` reaches {len(ctx.api_endpoints)} components."

    # ========================================================================
    # STATE CONTEXT
    # ========================================================================
    
    async def _build_state_context(self, ctx: ExplainContext, entity: dict):
        """Build state management flow."""
        fqn = entity.get("fqn")
        
        query = """
        MATCH (widget {project_id: $project_id})-[:CONTAINS|DEPENDS_ON|IMPORTS*1..3]->(dep {project_id: $project_id})
        WHERE widget.name CONTAINS $name OR dep.name CONTAINS $name
        RETURN widget.name AS widget, dep.name AS provider
        LIMIT 10
        """
        records = await self.graph_client.execute(query, {"name": entity.get("name", ""), "project_id": self.project_id})
        
        ctx.state_flow = [dict(r) for r in records]
        ctx.overview = f"State flow for `{entity.get('name')}` has {len(ctx.state_flow)} related components."

    # ========================================================================
    # SEMANTIC CONTEXT (fallback)
    # ========================================================================
    
    async def _build_semantic_context(self, ctx: ExplainContext, entity: dict, search_results=None):
        """Build context from semantic search + graph neighbors."""
        # Get callers/callees
        fqn = entity.get("fqn")
        rel_query = """
        MATCH (e {fqn: $fqn, project_id: $project_id})
        OPTIONAL MATCH (caller {project_id: $project_id})-[:CALLS]->(e)
        OPTIONAL MATCH (e)-[:CALLS]->(callee {project_id: $project_id})
        RETURN collect(DISTINCT caller.name) AS callers,
               collect(DISTINCT callee.name) AS callees
        """
        records = await self.graph_client.execute(rel_query, {"fqn": fqn, "project_id": self.project_id})
        if records:
            ctx.dependency_graph[entity.get("name", "")] = [
                (c, "CALLS") for c in (records[0].get("callers") or [])
            ] + [(c, "CALLED_BY") for c in (records[0].get("callees") or [])]
        
        ctx.overview = f"`{entity.get('name')}` is a {entity.get('type', 'entity')} in the codebase."

    # ========================================================================
    # CONTEXT FORMATTING
    # ========================================================================
    
    def _format_context(self, ctx: ExplainContext) -> str:
        """Format ExplainContext into a structured LLM prompt."""
        parts = []
        
        # Header
        parts.append(f"## EXPLANATION: {ctx.query.upper()}")
        parts.append(f"**Intent**: {ctx.intent.value}")
        if ctx.feature:
            parts.append(f"**Feature**: {ctx.feature}")
        parts.append("")
        
        # Overview
        if ctx.overview:
            parts.append(f"### OVERVIEW\n{ctx.overview}\n")
        
        # Workflow Chain
        if ctx.workflow_chain:
            parts.append("### WORKFLOW CHAIN")
            for h in ctx.workflow_chain[:15]:
                from_n = h.get('from', h.get('name', '?'))
                to_n = h.get('to', '')
                rel = h.get('relationship', '')
                etype = h.get('type', '')
                if to_n:
                    parts.append(f"- **{from_n}** ({etype}) --{rel}--> **{to_n}**")
                else:
                    parts.append(f"- **{from_n}** ({etype})")
            parts.append("")
        
        # Dependency Graph
        if ctx.dependency_graph:
            parts.append("### DEPENDENCY GRAPH")
            for dep_name, deps in list(ctx.dependency_graph.items())[:10]:
                parts.append(f"**{dep_name}**")
                for dep_type, rel_type in deps[:5]:
                    parts.append(f"  ├── {rel_type} → {dep_type}")
            parts.append("")
        
        # State Flow
        if ctx.state_flow:
            parts.append("### STATE FLOW")
            for sf in ctx.state_flow[:5]:
                parts.append(f"- {sf.get('widget', '?')} → {sf.get('provider', '?')} → {sf.get('repo', '?')}")
            parts.append("")
        
        # API Endpoints
        if ctx.api_endpoints:
            parts.append("### API ENDPOINTS")
            for ep in ctx.api_endpoints[:10]:
                parts.append(f"- {ep.get('endpoint', '?')}")
            parts.append("")
        
        # Important Entities
        if ctx.important_entities:
            parts.append("### KEY ENTITIES")
            for e in ctx.important_entities[:10]:
                parts.append(f"- **{e.get('name', '?')}** ({e.get('type', '?')}) — `{e.get('file_path', e.get('fqn', ''))}`")
            parts.append("")
        
        # Important Files
        if ctx.important_files:
            parts.append("### IMPORTANT FILES")
            for f in ctx.important_files[:5]:
                parts.append(f"- `{f}`")
            parts.append("")
        
        return "\n".join(parts)
    def _generate_suggestions(self, ctx: ExplainContext) -> list[str]:
        """Generate contextual suggestions for further exploration."""
        suggestions = []
        
        if ctx.workflow_chain:
            names = [h['name'] for h in ctx.workflow_chain[:3] if h.get('name')]
            if names:
                suggestions.append(f"Trace full workflow: `repo trace {names[0]}`")
        
        if ctx.dependency_graph:
            dep_names = list(ctx.dependency_graph.keys())[:2]
            for dn in dep_names:
                suggestions.append(f"Analyze dependencies of `{dn}`: `repo impact {dn}`")
        
        if ctx.feature:
            suggestions.append(f"View feature architecture: `repo architecture --module {ctx.feature}`")
        
        if ctx.state_flow:
            suggestions.append(f"Check state coupling: `repo metrics --module {ctx.feature or 'current'}`")
        
        return suggestions[:5]