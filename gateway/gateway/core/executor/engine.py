"""Parallel execution engine."""

import asyncio
import time
from typing import Any

import structlog

from gateway.core.executor.circuit_breaker import get_circuit_breaker
from gateway.core.executor.models import ExecutorResult
from gateway.core.planner.models import Plan, SourceQuery
from gateway.core.sources.models import SourceResponse
from gateway.core.sources.registry import get_source_registry

logger = structlog.get_logger(__name__)


class ExecutorEngine:
    """Engine to execute retrieval plans."""

    def __init__(self):
        self.source_registry = get_source_registry()
        self.circuit_breaker = get_circuit_breaker()

    async def execute(self, plan: Plan) -> ExecutorResult:
        """Execute all queries in the plan with parallelism."""
        start_time = time.time()
        all_responses: list[SourceResponse] = []

        for step in plan.steps:
            if not self._should_execute_step(step):
                continue

            if step.parallel:
                # Execute all queries in step in parallel
                tasks = [
                    self._execute_single_query(query)
                    for query in step.queries
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Execute sequentially
                responses = []
                for query in step.queries:
                    try:
                        resp = await self._execute_single_query(query)
                        responses.append(resp)
                    except Exception as e:
                        logger.warning("Sequential query failed", query=query, error=str(e))
                        responses.append(e)

            # Process responses
            for resp in responses:
                if isinstance(resp, Exception):
                    logger.warning("Source query failed", error=str(resp))
                else:
                    all_responses.append(resp)

        total_latency_ms = int((time.time() - start_time) * 1000)
        success_count = sum(1 for r in all_responses if r.success)
        failure_count = len(all_responses) - success_count

        return ExecutorResult(
            source_responses=all_responses,
            total_latency_ms=total_latency_ms,
            success_count=success_count,
            failure_count=failure_count
        )

    async def _execute_single_query(self, query: SourceQuery) -> SourceResponse:
        """Execute a single source query."""
        source = self.source_registry.get_source(query.source)

        if not source:
            return SourceResponse(
                source=query.source,
                query_type=query.query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=0,
                success=False,
                error=f"Source {query.source} not found"
            )

        if self.circuit_breaker.is_open(query.source):
            return SourceResponse(
                source=query.source,
                query_type=query.query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=0,
                success=False,
                error=f"Circuit breaker open for {query.source}"
            )

        try:
            response = await asyncio.wait_for(
                source.query(query.query_type, query.query_params),
                timeout=query.timeout_seconds
            )
            if response.success:
                self.circuit_breaker.record_success(query.source)
            else:
                self.circuit_breaker.record_failure(query.source)
            return response
        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure(query.source)
            return SourceResponse(
                source=query.source,
                query_type=query.query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=int(query.timeout_seconds * 1000),
                success=False,
                error=f"Timeout after {query.timeout_seconds}s"
            )
        except Exception as e:
            self.circuit_breaker.record_failure(query.source)
            return SourceResponse(
                source=query.source,
                query_type=query.query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=0,
                success=False,
                error=str(e)
            )

    def _should_execute_step(self, step) -> bool:
        """Check if a retrieval step should be executed."""
        if step.condition in {"always", "", None}:
            return True
        logger.debug("Skipping retrieval step with unmet condition", condition=step.condition)
        return False


async def execute(plan: Plan) -> ExecutorResult:
    """Convenience function to execute a plan."""
    engine = ExecutorEngine()
    return await engine.execute(plan)
