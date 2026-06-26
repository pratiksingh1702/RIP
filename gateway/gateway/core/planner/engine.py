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

        # Build retrieval steps
        steps = [
            RetrievalStep(
                queries=queries,
                parallel=True,
                condition="always"
            )
        ]

        # Allocate token budget
        token_allocation = allocate_token_budget(
            total_budget=max_tokens,
            token_weights=strategy["token_weights"],
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

        return SourceQuery(
            source=source,
            query_type=query_type,
            query_params=query_params,
            priority=priority,
            estimated_tokens=estimated_tokens,
            timeout_seconds=settings.source_timeout_seconds
        )

    def _condition_matches(self, condition: str, task: str) -> bool:
        """Evaluate lightweight retrieval conditions without side effects."""
        if condition == "always":
            return True
        if condition == "ticket_number_in_task":
            return self._extract_ticket(task) is not None
        if condition == "files_overlap_with_active_prs":
            return True
        return False

    def _extract_ticket(self, task: str) -> str | None:
        """Extract common Jira-style ticket identifiers from task text."""
        import re

        match = re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", task)
        return match.group(0) if match else None


def plan(classification: ClassificationResult, task: str, max_tokens: int = settings.default_max_tokens) -> Plan:
    """Convenience function to create a plan."""
    engine = PlannerEngine()
    return engine.plan(classification, task, max_tokens)
