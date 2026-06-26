"""Multi-source planner engine."""

from datetime import datetime
from typing import Any

from gateway.config import settings
from gateway.core.classifier.models import ClassificationResult, IntentType
from gateway.core.planner.budget import allocate_token_budget
from gateway.core.planner.models import Plan, RetrievalStep, SourceQuery
from gateway.core.planner.strategies import STRATEGY_TABLE


class PlannerEngine:
    """Planner that creates retrieval plans from classification results."""

    def __init__(self):
        self.enabled_sources = ["rip"]  # RIP is always enabled

    def plan(
        self,
        classification: ClassificationResult,
        task: str,
        max_tokens: int = settings.default_max_tokens
    ) -> Plan:
        """Create a retrieval plan for the given classification and task."""
        # Get strategy
        strategy = STRATEGY_TABLE.get(classification.intent, STRATEGY_TABLE[IntentType.INVESTIGATION])

        # Build queries
        queries = []

        # Always-query sources (RIP only for now, others optional later
        for query_spec in strategy["always_query"]:
            if query_spec["source"] in self.enabled_sources:
                queries.append(
                    self._build_query(
                        source=query_spec["source"],
                        query_type=query_spec["type"],
                        task=task,
                        priority=1,
                        estimated_tokens=1500
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
            enabled_sources=self.enabled_sources
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
        if source == "rip":
            query_params["task"] = task
            if query_type in ["search", "trace", "explain"]:
                query_params["query"] = task

        return SourceQuery(
            source=source,
            query_type=query_type,
            query_params=query_params,
            priority=priority,
            estimated_tokens=estimated_tokens,
            timeout_seconds=settings.source_timeout_seconds
        )


def plan(classification: ClassificationResult, task: str, max_tokens: int = settings.default_max_tokens) -> Plan:
    """Convenience function to create a plan."""
    engine = PlannerEngine()
    return engine.plan(classification, task, max_tokens)
