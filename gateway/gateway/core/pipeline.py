"""End-to-end pipeline orchestrator (Phase 10)."""

import re
from typing import Any

import structlog

from gateway.config import settings
from gateway.core.classifier.engine import ClassifierEngine
from gateway.core.events import PipelineEventSink, get_pipeline_event_bus
from gateway.core.events.bus import get_event_bus
from gateway.core.executor.engine import ExecutorEngine
from gateway.core.memory.conflict_detector import ConflictDetector
from gateway.core.memory.store import SessionStore
from gateway.core.permissions import PermissionEngine, UserRole
from gateway.core.planner.engine import PlannerEngine
from gateway.core.ranker.engine import RankerEngine
from gateway.core.sources.models import SourceResponse
from gateway.core.sources.registry import get_source_registry
from gateway.server.schemas.common import ContextItem, ContextPackage
from gateway.storage.source_registry import get_gateway_settings

logger = structlog.get_logger(__name__)


class GatewayPipeline:
    """End-to-end pipeline for context gateway."""

    def __init__(self):
        self.classifier = ClassifierEngine()
        self.planner = PlannerEngine()
        self.executor = ExecutorEngine()
        self.ranker = RankerEngine()
        self.permissions = PermissionEngine()
        self.session_store = SessionStore()
        self.conflict_detector = ConflictDetector()
        self.source_registry = get_source_registry()

    async def get_context(
        self,
        task: str,
        max_tokens: int = settings.default_max_tokens,
        role: str = "developer",
        trace_session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        event_sink: PipelineEventSink | None = None,
    ) -> ContextPackage:
        """Run full pipeline to get context."""
        logger.info("Starting context pipeline", task=task, max_tokens=max_tokens, role=role, project_id=project_id, user_id=user_id)
        await self.source_registry.refresh(project_id=project_id, user_id=user_id)
        editable_settings = await get_gateway_settings()
        logger.debug("Using gateway settings", settings=editable_settings)
        if max_tokens == settings.default_max_tokens:
            max_tokens = int(editable_settings["default_max_tokens"])
        if role == "developer":
            role = str(editable_settings["default_role"])

        # Step 1: Classify intent (no session yet)
        logger.info("Starting intent classification")
        classification = await self.classifier.classify_async(task)
        logger.info(
            "Classification complete",
            intent=classification.intent,
            domain=classification.domain,
            confidence=classification.confidence,
            risk_level=classification.risk_level
        )

        # Step 2: Create session first, so emit can use session_id
        logger.info("Creating session")
        session = await self.session_store.create_session(
            agent_type="mcp_agent",
            task=task,
            classification=classification
        )
        session_id = str(session.id)
        logger.info("Session created", session_id=session_id)

        async def emit(event: dict[str, Any]) -> None:
            # First, handle existing pipeline event sink/old bus
            if event_sink is not None:
                await event_sink(event)
            if trace_session_id:
                await get_pipeline_event_bus().emit(
                    trace_session_id,
                    stage=str(event["stage"]),
                    status=str(event["status"]),
                    detail=str(event["detail"]),
                    source=event.get("source"),
                    meta=event.get("meta") or {},
                )
            # Now publish to new event bus
            event_bus = get_event_bus()
            await event_bus.publish(
                event_type=str(event["stage"]),
                project_id=project_id,
                session_id=session_id,
                payload={
                    "status": event["status"],
                    "detail": event["detail"],
                    "source": event.get("source"),
                    "meta": event.get("meta") or {},
                },
            )

        # Now emit the intent events now that session exists
        await emit({
            "stage": "intent",
            "status": "started",
            "detail": "Reading your request",
            "meta": {},
        })
        await emit({
            "stage": "intent",
            "status": "done",
            "detail": (
                f"{classification.intent.value} - {classification.domain} domain - "
                f"{int(classification.confidence * 100)}% confidence"
            ),
            "meta": {
                "intent": classification.intent.value,
                "domain": classification.domain,
                "confidence": classification.confidence,
                "risk": classification.risk_level.value,
            },
        })

        # Step 3: Plan retrieval
        logger.info("Starting retrieval planning")
        plan = self.planner.plan(classification, task, max_tokens, project_id=project_id)
        await emit({
            "stage": "plan",
            "status": "done",
            "detail": (
                f"Planning retrieval - {len(plan.token_allocation)} sources, "
                f"{max_tokens:,} token budget"
            ),
            "meta": {
                "sources": list(plan.token_allocation),
                "token_budget": max_tokens,
                "token_allocation": plan.token_allocation,
            },
        })
        logger.info(
            "Plan created", 
            steps=len(plan.steps), 
            token_allocation=plan.token_allocation,
            plan=plan
        )

        # Step 4: Execute retrieval
        logger.info("Starting plan execution")
        execution_result = await self.executor.execute(plan, event_sink=emit)
        logger.info(
            "Execution complete",
            success_count=execution_result.success_count,
            failure_count=execution_result.failure_count,
            total_latency=execution_result.total_latency_ms,
            sources_used=[r.source for r in execution_result.source_responses]
        )

        files_accessed = self._extract_files_from_responses(execution_result.source_responses)
        await self.session_store.update_files_accessed(session.id, files_accessed)
        logger.debug("Files accessed in session", files_accessed=files_accessed)

        # Step 5: Detect conflicts before final formatting so warnings are visible.
        logger.info("Checking for conflicts")
        await emit({
            "stage": "conflict_check",
            "status": "started",
            "detail": "Checking for conflicts with active sessions",
            "meta": {"files": files_accessed},
        })
        conflicts = await self.conflict_detector.detect(session.id, files_accessed)
        if conflicts:
            logger.warning("Conflicts detected", conflicts=conflicts)
            await emit({
                "stage": "conflict_found",
                "status": "done",
                "detail": self._conflict_detail(conflicts),
                "meta": {"count": len(conflicts)},
            })
        else:
            logger.info("No conflicts found")
            await emit({
                "stage": "conflict_check",
                "status": "done",
                "detail": "No active file conflicts found",
                "meta": {"count": 0},
            })

        # Step 6: Rank and compress
        successful_responses = [
            response for response in execution_result.source_responses if response.success
        ]
        logger.info("Starting ranking and compression", candidates=len(successful_responses))
        await emit({
            "stage": "rank",
            "status": "started",
            "detail": f"Scoring {len(successful_responses)} candidates",
            "meta": {"count": len(successful_responses)},
        })
        ranked = await self.ranker.rank_and_compress(
            execution_result.source_responses,
            classification,
            task,
            max_tokens
        )
        removed = max(0, len(successful_responses) - len(ranked.included) - len(ranked.excluded))
        if removed:
            logger.debug("Removed duplicate items", count=removed)
            await emit({
                "stage": "dedup",
                "status": "done",
                "detail": f"Removed {removed} duplicate items",
                "meta": {"removed": removed},
            })
        await emit({
            "stage": "compress",
            "status": "done",
            "detail": f"Compressed to {ranked.tokens_used:,} of {ranked.token_budget:,} tokens",
            "meta": {
                "before_tokens": sum(response.token_count for response in successful_responses),
                "after_tokens": ranked.tokens_used,
                "token_budget": ranked.token_budget,
            },
        })
        logger.info("Ranking complete", included=len(ranked.included), excluded=len(ranked.excluded))

        # Step 7: Apply permissions
        user_role = self._coerce_role(role)
        logger.info("Applying permissions filters", role=user_role, domain=classification.domain)
        filtered = await self.permissions.filter_context(
            ranked.included,
            user_role,
            classification.domain,
            session_id=session_id
        )
        filtered_count = max(0, len(ranked.included) - len(filtered))
        if filtered_count:
            logger.info("Filtered context items", count=filtered_count, role=user_role.value)
            await emit({
                "stage": "permission_filter",
                "status": "done",
                "detail": f"Applied {user_role.value} access rules",
                "meta": {"filtered": filtered_count, "role": user_role.value},
            })

        # Build context package
        context_items = [
            ContextItem(
                source=item.source,
                query_type=item.query_type,
                content=item.content,
                metadata=item.metadata,
                score=item.score
            )
            for item in filtered
        ]

        warnings = self._build_warnings(execution_result.source_responses)
        tokens_retrieved = sum(
            response.token_count for response in execution_result.source_responses
        )
        await self.session_store.update_session_stats(
            session.id,
            sources_used=[
                response.source for response in execution_result.source_responses
            ],
            tokens_retrieved=tokens_retrieved,
            tokens_delivered=ranked.tokens_used,
        )
        await emit({
            "stage": "done",
            "status": "done",
            "detail": "Answer context ready",
            "meta": {
                "context_items": len(context_items),
                "tokens_used": ranked.tokens_used,
            },
        })

        logger.info(
            "Pipeline complete",
            session_id=session_id,
            context_items=len(context_items),
            tokens_used=ranked.tokens_used,
            tokens_retrieved=tokens_retrieved,
            conflicts=len(conflicts),
            warnings=len(warnings)
        )

        return ContextPackage(
            session_id=session_id,
            intent=classification.intent.value,
            domain=classification.domain,
            context=context_items,
            tokens_used=ranked.tokens_used,
            tokens_retrieved=tokens_retrieved,
            token_allocation=plan.token_allocation,
            score_summary=self._score_summary(ranked.included),
            conflicts=[conflict.model_dump(mode="json") for conflict in conflicts],
            warnings=warnings
        )

    def _coerce_role(self, role: str) -> UserRole:
        """Use configured default role if the caller sends an unknown value."""
        try:
            return UserRole(role)
        except ValueError:
            logger.warning("Unknown role supplied, using default", role=role)
            return UserRole(settings.default_role)

    def _extract_files_from_responses(self, responses: list[SourceResponse]) -> list[str]:
        """Extract file paths from source metadata and text content."""
        files: set[str] = set()
        for response in responses:
            metadata_files = response.metadata.get("files", [])
            if isinstance(metadata_files, list):
                files.update(str(path) for path in metadata_files if path)
            elif isinstance(metadata_files, str):
                files.add(metadata_files)

            affected = response.metadata.get("affected_files", [])
            if isinstance(affected, list):
                files.update(str(path) for path in affected if path)

            files.update(self._extract_file_paths(response.content))

        return sorted(self._normalize_file_path(path) for path in files if path)

    def _extract_file_paths(self, content: str) -> set[str]:
        patterns = [
            r"[\w./\\-]+\.(?:py|ts|tsx|js|jsx|dart|java|go|rs|md|toml|yaml|yml|json)",
            r"[A-Za-z]:\\[^\s:]+?\.(?:py|ts|tsx|js|jsx|dart|java|go|rs|md|toml|yaml|yml|json)",
        ]
        files: set[str] = set()
        for pattern in patterns:
            for match in re.findall(pattern, content):
                files.add(match.strip("`'\".,;)"))
        return files

    def _normalize_file_path(self, path: str) -> str:
        return path.replace("\\", "/").strip()

    def _build_warnings(self, responses: list[SourceResponse]) -> list[str]:
        warnings = []
        for response in responses:
            if not response.success:
                reason = response.error or "source query failed"
                warnings.append(f"{response.source}/{response.query_type}: {reason}")
        return warnings

    def _score_summary(self, items) -> list[dict[str, Any]]:
        return [
            {
                "source": item.source,
                "query_type": item.query_type,
                "score": item.score,
                "metadata": item.metadata,
            }
            for item in items[:5]
        ]

    def _conflict_detail(self, conflicts) -> str:
        first = conflicts[0]
        files = getattr(first, "overlapping_files", None) or []
        if files:
            return f"{files[0]} is being edited in another active session"
        return "A file conflict was found with another active session"


# Global pipeline instance
_pipeline: GatewayPipeline | None = None


def get_context_pipeline() -> GatewayPipeline:
    """Get the global context pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = GatewayPipeline()
    return _pipeline

