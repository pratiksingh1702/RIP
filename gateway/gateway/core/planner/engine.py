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
        max_tokens: int = settings.default_max_tokens
    ) -> Plan:
        """Create a retrieval plan for the given classification and task."""
        # Get strategy
        strategy = STRATEGY_TABLE.get(classification.intent, STRATEGY_TABLE[IntentType.INVESTIGATION])
        enabled_sources = self.source_registry.enabled_source_names()

        # Build queries
        queries = []

        # Always-query sources.
        for query_spec in strategy["always_query"]:
            if query_spec["source"] in enabled_sources:
                queries.append(
                    self._build_query(
                        source=query_spec["source"],
                        query_type=query_spec["type"],
                        task=task,
                        priority=1,
                        estimated_tokens=1500
                    )
                )
        queries = self._require_rip_explain(queries, enabled_sources, task)

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
                    priority=2,
                    estimated_tokens=1000,
                )
            )
        queries.extend(self._dynamic_source_queries(classification, task, enabled_sources))

        # Build retrieval steps. Keep the required RIP explain query first so the
        # most reliable context path is available before broader probes run.
        steps = self._build_retrieval_steps(queries)

        # Allocate token budget
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
        priority: int,
        estimated_tokens: int
    ) -> SourceQuery:
        """Build a source query with appropriate parameters."""
        query_params: dict[str, Any] = {}
        query_params["task"] = task
        query_params["query"] = task
        if source == "rip":
            query_params["limit"] = 10
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
    ) -> list[SourceQuery]:
        """Make RIP explain the required first context query whenever RIP is enabled."""
        if "rip" not in enabled_sources:
            return queries

        explain_query = self._build_query(
            source="rip",
            query_type="explain",
            task=task,
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
    ) -> list[SourceQuery]:
        """Add runtime MCP sources using domain hints without rewriting strategies."""
        queries: list[SourceQuery] = []
        domain_terms = {
            classification.domain.lower(),
            *(keyword.lower() for keyword in classification.domain_keywords_found),
        }
        task_lower = task.lower()
        for record in self.source_registry.dynamic_source_records():
            if record.name not in enabled_sources:
                continue
            hints = {hint.lower() for hint in record.domain_hints}
            matched = bool(hints & domain_terms) or any(hint in task_lower for hint in hints)
            queries.append(
                self._build_query(
                    source=record.name,
                    query_type="search",
                    task=task,
                    priority=2 if matched else 3,
                    estimated_tokens=1000 if matched else 600,
                )
            )
        return queries

    def _token_weights_with_dynamic_sources(
        self,
        base_weights: dict[str, float],
        queries: list[SourceQuery],
    ) -> dict[str, float]:
        """Give dynamic sources modest allocation without changing built-in weights."""
        weights = dict(base_weights)
        for query in queries:
            if query.source not in weights:
                weights[query.source] = 0.10 if query.priority <= 2 else 0.05
        return weights

    def _extract_ticket(self, task: str) -> str | None:
        """Extract common Jira-style ticket identifiers from task text."""
        import re

        match = re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", task)
        return match.group(0) if match else None


def plan(classification: ClassificationResult, task: str, max_tokens: int = settings.default_max_tokens) -> Plan:
    """Convenience function to create a plan."""
    engine = PlannerEngine()
    return engine.plan(classification, task, max_tokens)
