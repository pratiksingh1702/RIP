"""Multi-source planner engine."""

from datetime import datetime
from typing import Any

from gateway.config import settings
from gateway.core.classifier.models import ClassificationResult, IntentType
from gateway.core.planner.budget import allocate_token_budget
from gateway.core.planner.models import Plan, RetrievalStep, SourceQuery
from gateway.core.planner.strategies import STRATEGY_TABLE
from gateway.core.sources.registry import get_source_registry


class PlannerEngine:
    """Planner that creates retrieval plans from classification results."""

    def __init__(self):
        self.source_registry = get_source_registry()

    def plan(
        self,
        classification: ClassificationResult,
        task: str,
        max_tokens: int = settings.default_max_tokens,
        project_id: str | None = None,
    ) -> Plan:
        """Create a retrieval plan for the given classification and task."""
        # Get strategy
        strategy = STRATEGY_TABLE.get(classification.intent, STRATEGY_TABLE[IntentType.INVESTIGATION])
        enabled_sources = self.source_registry.enabled_source_names(project_id=project_id)

        # Build queries
        queries = []

        # Always-query sources — workspace_memory is always included
        for query_spec in strategy["always_query"]:
            if query_spec["source"] in enabled_sources:
                queries.append(
                    self._build_query(
                        source=query_spec["source"],
                        query_type=query_spec["type"],
                        task=task,
                        project_id=project_id,
                        priority=1,
                        estimated_tokens=1500
                    )
                )
        
        # Workspace Memory — always queried for past knowledge
        if "workspace_memory" in enabled_sources:
            queries.append(
                self._build_query(
                    source="workspace_memory",
                    query_type="search",
                    task=task,
                    project_id=project_id,
                    priority=1,
                    estimated_tokens=500,
                )
            )
        
        queries = self._require_rip_explain(queries, enabled_sources, task, project_id)

        # Conditional sources only run when their source is enabled and condition is met.
        for query_spec in strategy.get("conditional_query", []):
            source = query_spec["source"]
            if source not in enabled_sources:
                continue
            if not self._condition_matches(query_spec.get("condition", "always"), task):
                continue
            queries.append(
                self._build_query(
                    source=source,
                    query_type=query_spec["type"],
                    task=task,
                    project_id=project_id,
                    priority=2,
                    estimated_tokens=1000,
                )
            )
        queries.extend(self._dynamic_source_queries(classification, task, enabled_sources, project_id))

        # Build retrieval steps
        steps = self._build_retrieval_steps(queries)

        # Allocate token budget — includes workspace_memory weight
        token_allocation = allocate_token_budget(
            total_budget=max_tokens,
            token_weights=self._token_weights_with_dynamic_sources(
                strategy["token_weights"],
                queries,
            ),
            enabled_sources=enabled_sources
        )

        # Estimate raw tokens
        estimated_tokens_raw = sum(q.estimated_tokens for q in queries)

        # Build plan
        return Plan(
            classification=classification,
            steps=steps,
            token_budget=max_tokens,
            token_allocation=token_allocation,
            estimated_tokens_raw=estimated_tokens_raw,
            created_at=datetime.utcnow()
        )

    def _build_query(
        self,
        source: str,
        query_type: str,
        task: str,
        project_id: str | None,
        priority: int,
        estimated_tokens: int
    ) -> SourceQuery:
        """Build a source query with appropriate parameters."""
        query_params: dict[str, Any] = {}
        query_params["task"] = task
        query_params["query"] = task
        if project_id:
            query_params["project_id"] = project_id
        if source == "rip":
            query_params["limit"] = 10
        elif source == "workspace_memory":
            query_params["limit"] = 5
        elif source == "jira":
            ticket = self._extract_ticket(task)
            if ticket:
                query_params["issue_key"] = ticket
        elif source == "github":
            query_params["limit"] = 10
        elif source == "slack":
            query_params["limit"] = 10
        else:
            query_params["limit"] = 10
            record = self.source_registry.get_record(source)
            if record is not None:
                query_params["source_id"] = record.id
                query_params["domain_hints"] = record.domain_hints

        return SourceQuery(
            source=source,
            query_type=query_type,
            query_params=query_params,
            priority=priority,
            estimated_tokens=estimated_tokens,
            timeout_seconds=settings.source_timeout_seconds
        )

    def _require_rip_explain(
        self,
        queries: list[SourceQuery],
        enabled_sources: list[str],
        task: str,
        project_id: str | None,
    ) -> list[SourceQuery]:
        """Make RIP explain the required first context query whenever RIP is enabled."""
        if "rip" not in enabled_sources:
            return queries

        explain_query = self._build_query(
            source="rip",
            query_type="explain",
            task=task,
            project_id=project_id,
            priority=1,
            estimated_tokens=2000,
        )
        remaining = [
            query
            for query in queries
            if not (query.source == "rip" and query.query_type == "explain")
        ]
        return [explain_query, *remaining]

    def _build_retrieval_steps(self, queries: list[SourceQuery]) -> list[RetrievalStep]:
        """Run required RIP explain first, then fan out to the remaining queries."""
        if not queries:
            return [RetrievalStep(queries=[], parallel=True, condition="always")]

        first = queries[0]
        if first.source == "rip" and first.query_type == "explain":
            steps = [
                RetrievalStep(
                    queries=[first],
                    parallel=False,
                    condition="always",
                )
            ]
            remaining = queries[1:]
            if remaining:
                steps.append(
                    RetrievalStep(
                        queries=remaining,
                        parallel=True,
                        condition="always",
                    )
                )
            return steps

        return [
            RetrievalStep(
                queries=queries,
                parallel=True,
                condition="always",
            )
        ]

    def _condition_matches(self, condition: str, task: str) -> bool:
        """Evaluate lightweight retrieval conditions without side effects."""
        if condition == "always":
            return True
        if condition == "ticket_number_in_task":
            return self._extract_ticket(task) is not None
        if condition == "files_overlap_with_active_prs":
            return True
        return False

    def _dynamic_source_queries(
        self,
        classification: ClassificationResult,
        task: str,
        enabled_sources: list[str],
        project_id: str | None,
    ) -> list[SourceQuery]:
        """Add runtime MCP sources using domain hints without rewriting strategies."""
        queries: list[SourceQuery] = []
        domain_terms = {
            classification.domain.lower(),
            *(keyword.lower() for keyword in classification.domain_keywords_found),
        }
        task_lower = task.lower()
        for record in self.source_registry.dynamic_source_records(project_id=project_id):
            if record.name not in enabled_sources:
                continue
            hints = {hint.lower() for hint in record.domain_hints}
            matched = bool(hints & domain_terms) or any(hint in task_lower for hint in hints)
            queries.append(
                self._build_query(
                    source=record.name,
                    query_type="search",
                    task=task,
                    project_id=project_id,
                    priority=2 if matched else 3,
                    estimated_tokens=1000 if matched else 600,
                )
            )
        return queries

    def plan_medium(self, classification, task: str, max_tokens: int = 6000, project_id: str | None = None) -> Plan:
        """Medium path: RIP + Memory + Knowledge. All parallel, no forced sequential explain."""
        enabled_sources = self.source_registry.enabled_source_names(project_id=project_id)
        queries = []
        for qs in [
            {"source": "workspace_memory", "type": "search", "priority": 1, "tokens": 500},
            {"source": "workspace_knowledge", "type": "search", "priority": 1, "tokens": 500},
            {"source": "rip", "type": "search", "priority": 1, "tokens": 1500},
        ]:
            if qs["source"] in enabled_sources or qs["source"] in ("workspace_memory", "workspace_knowledge"):
                queries.append(self._build_query(source=qs["source"], query_type=qs["type"], task=task, project_id=project_id, priority=qs["priority"], estimated_tokens=qs["tokens"]))
        steps = [RetrievalStep(queries=queries, parallel=True, condition="always")]
        token_allocation = allocate_token_budget(total_budget=max_tokens, token_weights={"rip": 0.50, "workspace_memory": 0.25, "workspace_knowledge": 0.25}, enabled_sources=list(set(q.source for q in queries)))
        return Plan(classification=classification, steps=steps, token_budget=max_tokens, token_allocation=token_allocation, estimated_tokens_raw=sum(q.estimated_tokens for q in queries), created_at=datetime.utcnow())

    def plan_deep(self, classification, task: str, max_tokens: int = 12000, project_id: str | None = None, role: str = "developer") -> Plan:
        """Deep path: Full pipeline with permission pre-filter."""
        from gateway.core.permissions.models import UserRole as UR
        try: user_role = UR(role)
        except ValueError: user_role = UR.DEVELOPER
        strategy = STRATEGY_TABLE.get(classification.intent, STRATEGY_TABLE[IntentType.INVESTIGATION])
        enabled_sources = self.source_registry.enabled_source_names(project_id=project_id)
        allowed_sources = self._pre_filter_sources(enabled_sources, user_role, classification.domain)
        queries = []
        for ws_source in ["workspace_memory", "workspace_knowledge"]:
            queries.append(self._build_query(source=ws_source, query_type="search", task=task, project_id=project_id, priority=1, estimated_tokens=500))
        if "rip" in allowed_sources:
            queries.append(self._build_query(source="rip", query_type="explain", task=task, project_id=project_id, priority=1, estimated_tokens=2000))
        for qs in strategy.get("always_query", []):
            if qs["source"] in allowed_sources and qs["source"] != "rip":
                queries.append(self._build_query(source=qs["source"], query_type=qs["type"], task=task, project_id=project_id, priority=1, estimated_tokens=1500))
        for qs in strategy.get("conditional_query", []):
            if qs["source"] in allowed_sources and self._condition_matches(qs.get("condition", "always"), task):
                queries.append(self._build_query(source=qs["source"], query_type=qs["type"], task=task, project_id=project_id, priority=2, estimated_tokens=1000))
        for record in self.source_registry.dynamic_source_records(project_id=project_id):
            if record.name in allowed_sources:
                queries.append(self._build_query(source=record.name, query_type="search", task=task, project_id=project_id, priority=2, estimated_tokens=600))
        explain_qs = [q for q in queries if q.source == "rip" and q.query_type == "explain"]
        other_qs = [q for q in queries if not (q.source == "rip" and q.query_type == "explain")]
        steps = []
        if explain_qs: steps.append(RetrievalStep(queries=explain_qs, parallel=False, condition="always"))
        if other_qs: steps.append(RetrievalStep(queries=other_qs, parallel=True, condition="always"))
        if not steps: steps = [RetrievalStep(queries=queries, parallel=True, condition="always")]
        weights = strategy.get("token_weights", {"rip": 0.50, "github": 0.25, "workspace_memory": 0.10, "workspace_knowledge": 0.10, "jira": 0.05})
        token_allocation = allocate_token_budget(total_budget=max_tokens, token_weights=weights, enabled_sources=list(set(q.source for q in queries)))
        return Plan(classification=classification, steps=steps, token_budget=max_tokens, token_allocation=token_allocation, estimated_tokens_raw=sum(q.estimated_tokens for q in queries), created_at=datetime.utcnow())

    def _pre_filter_sources(self, enabled_sources: list[str], role, domain: str) -> list[str]:
        """Permission pre-filter: remove blocked sources BEFORE retrieval."""
        from gateway.core.permissions.roles import DEFAULT_POLICIES, SENSITIVE_DOMAINS
        from gateway.core.permissions.models import UserRole as UR
        policy = DEFAULT_POLICIES.get(role, DEFAULT_POLICIES.get(UR.DEVELOPER))
        if not policy: return enabled_sources
        allowed = []
        for source in enabled_sources:
            if source in ("rip", "workspace_memory", "workspace_knowledge", "workspace_goals", "entity_graph"):
                allowed.append(source); continue
            source_ok = "*" in (getattr(policy, 'allowed_sources', []) or []) or source in (getattr(policy, 'allowed_sources', []) or [])
            domain_ok = not (domain in SENSITIVE_DOMAINS) or getattr(policy, 'can_access_sensitive_domains', True)
            if source_ok and domain_ok: allowed.append(source)
        return allowed

    def _token_weights_with_dynamic_sources(
        self,
        base_weights: dict[str, float],
        queries: list[SourceQuery],
    ) -> dict[str, float]:
        """Give dynamic sources modest allocation without changing built-in weights."""
        weights = dict(base_weights)
        # Ensure workspace_memory always has a weight
        if "workspace_memory" not in weights:
            weights["workspace_memory"] = 0.10
        for query in queries:
            if query.source not in weights:
                weights[query.source] = 0.10 if query.priority <= 2 else 0.05
        return weights

    def _extract_ticket(self, task: str) -> str | None:
        """Extract common Jira-style ticket identifiers from task text."""
        import re
        match = re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", task)
        return match.group(0) if match else None


def plan(
    classification: ClassificationResult,
    task: str,
    max_tokens: int = settings.default_max_tokens,
    project_id: str | None = None,
) -> Plan:
    """Convenience function to create a plan."""
    engine = PlannerEngine()
    return engine.plan(classification, task, max_tokens, project_id=project_id)
