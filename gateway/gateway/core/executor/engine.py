"""Parallel execution engine."""

import asyncio
import time
from typing import Any

import structlog

from gateway.core.events import PipelineEventSink
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

    async def execute(
        self,
        plan: Plan,
        event_sink: PipelineEventSink | None = None,
    ) -> ExecutorResult:
        """Execute all queries in the plan with parallelism."""
        start_time = time.time()
        all_responses: list[SourceResponse] = []

        for step in plan.steps:
            if not self._should_execute_step(step):
                continue

            if step.parallel:
                # Execute all queries in step in parallel
                tasks = [
                    self._execute_single_query(query, event_sink=event_sink)
                    for query in step.queries
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Execute sequentially
                responses = []
                for query in step.queries:
                    try:
                        resp = await self._execute_single_query(
                            query,
                            event_sink=event_sink,
                        )
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

    async def _execute_single_query(
        self,
        query: SourceQuery,
        event_sink: PipelineEventSink | None = None,
    ) -> SourceResponse:
        """Execute a single source query."""
        source = self.source_registry.get_source(query.source)
        logger.info("Starting source query", source=query.source, query_type=query.query_type, query_params=query.query_params)
        if not source:
            logger.error("Source not found", source=query.source)
            response = SourceResponse(
                source=query.source,
                query_type=query.query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=0,
                success=False,
                error=f"Source {query.source} not found"
            )
            await self._emit_source_event(response, event_sink)
            return response

        if self.circuit_breaker.is_open(query.source):
            logger.warning("Circuit breaker open, skipping query", source=query.source)
            response = SourceResponse(
                source=query.source,
                query_type=query.query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=0,
                success=False,
                error=f"Circuit breaker open for {query.source}"
            )
            await self._emit_source_event(response, event_sink, skipped=True)
            return response

        try:
            if event_sink is not None:
                await event_sink({
                    "stage": "source_start",
                    "source": query.source,
                    "status": "started",
                    "detail": self._source_start_detail(query),
                    "meta": {"query_type": query.query_type},
                })
            query_start_time = time.time()
            logger.info(
                "Calling source query", 
                source=query.source, 
                query_type=query.query_type, 
                params=query.query_params,
                timeout_seconds=query.timeout_seconds
            )
            response = await asyncio.wait_for(
                source.query(query.query_type, query.query_params),
                timeout=query.timeout_seconds
            )
            query_end_time = time.time()
            actual_latency_ms = int((query_end_time - query_start_time) * 1000)
            logger.info(
                "Source query returned", 
                source=query.source,
                query_type=response.query_type,
                success=response.success,
                token_count=response.token_count,
                latency_ms=response.latency_ms,
                actual_latency_ms=actual_latency_ms
            )
            if response.success:
                self.circuit_breaker.record_success(query.source)
            else:
                self.circuit_breaker.record_failure(query.source)
                logger.warning(
                    "Source query failed", 
                    source=query.source, 
                    error=response.error
                )
            await self._emit_source_event(response, event_sink)
            return response
        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure(query.source)
            query_end_time = time.time()
            actual_latency_ms = int((query_end_time - query_start_time) * 1000)
            logger.error(
                "Source query timed out", 
                source=query.source, 
                timeout_seconds=query.timeout_seconds,
                actual_latency_ms=actual_latency_ms
            )
            response = SourceResponse(
                source=query.source,
                query_type=query.query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=int(query.timeout_seconds * 1000),
                success=False,
                error=f"Timeout after {query.timeout_seconds}s"
            )
            await self._emit_source_event(response, event_sink)
            return response
        except Exception as e:
            self.circuit_breaker.record_failure(query.source)
            query_end_time = time.time()
            actual_latency_ms = int((query_end_time - query_start_time) * 1000)
            logger.error(
                "Source query failed with exception", 
                source=query.source, 
                error=str(e), 
                traceback=True
            )
            response = SourceResponse(
                source=query.source,
                query_type=query.query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=actual_latency_ms,
                success=False,
                error=str(e)
            )
            await self._emit_source_event(response, event_sink)
            return response

    def _should_execute_step(self, step) -> bool:
        """Check if a retrieval step should be executed."""
        if step.condition in {"always", "", None}:
            return True
        logger.debug("Skipping retrieval step with unmet condition", condition=step.condition)
        return False

    async def _emit_source_event(
        self,
        response: SourceResponse,
        event_sink: PipelineEventSink | None,
        *,
        skipped: bool = False,
    ) -> None:
        if event_sink is None:
            return
        if skipped:
            stage = "source_skipped"
            status = "skipped"
            detail = f"{self._source_label(response.source)} - skipped ({response.error})"
        elif response.success:
            stage = "source_done"
            status = "done"
            requested_query_type = response.metadata.get("requested_query_type")
            fallback_note = ""
            if requested_query_type and requested_query_type != response.query_type:
                fallback_note = f" via {response.query_type} fallback"
            detail = (
                f"{self._source_label(response.source)} - "
                f"{response.token_count} tokens in {response.latency_ms}ms"
                f"{fallback_note}"
            )
        else:
            stage = "source_failed"
            status = "failed"
            detail = (
                f"{self._source_label(response.source)} - "
                f"{response.error or 'failed'}, continuing without it"
            )
        await event_sink({
            "stage": stage,
            "source": response.source,
            "status": status,
            "detail": detail,
            "meta": {
                "query_type": response.query_type,
                "count": 1 if response.success and response.content else 0,
                "ms": response.latency_ms,
                "tokens": response.token_count,
                "error": response.error,
                "requested_query_type": response.metadata.get("requested_query_type"),
                "fallback_attempts": response.metadata.get("fallback_attempts", []),
            },
        })

    def _source_start_detail(self, query: SourceQuery) -> str:
        label = self._source_label(query.source)
        if query.source == "rip":
            return "Querying RIP graph..."
        record = self.source_registry.get_record(query.source)
        if record is not None and record.kind == "mcp":
            return f"Searching {label} MCP source..."
        return f"Searching {label}..."

    def _source_label(self, source: str) -> str:
        return {
            "rip": "RIP graph",
            "github": "GitHub",
            "jira": "Jira",
            "slack": "Slack",
        }.get(source, source)


async def execute(plan: Plan) -> ExecutorResult:
    """Convenience function to execute a plan."""
    engine = ExecutorEngine()
    return await engine.execute(plan)
