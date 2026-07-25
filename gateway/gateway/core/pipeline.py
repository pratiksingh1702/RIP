"""End-to-end pipeline orchestrator (Phase 10)."""

import re
from typing import Any
from uuid import uuid4
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
from gateway.core.ranker.models import ScoredItem
from gateway.core.router import get_router, get_route_feedback, PathType
from gateway.core.security import get_provenance_tagger, get_injection_scanner
from gateway.core.sources.models import SourceResponse
from gateway.core.sources.registry import get_source_registry
from gateway.core.workspace.goals import get_goal_engine
from gateway.core.workspace.knowledge import get_workspace_knowledge
from gateway.core.workspace.memory import get_workspace_memory
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
        max_tokens: int | None = None,
        role: str = "developer",
        trace_session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        event_sink=None,
    ) -> ContextPackage:
        """Route to fast/medium/deep path based on Router LLM decision."""
        if max_tokens is None:
            editable_settings = await get_gateway_settings()
            max_tokens = int(editable_settings.get("default_max_tokens", 12000))
            role = str(editable_settings.get("default_role", role))

        await self.source_registry.refresh(project_id=project_id, user_id=user_id)

        router = get_router()
        decision = await router.route(task, project_id, user_id, role)
        get_route_feedback().log_route(task, decision, project_id, user_id)

        logger.info(
            "Routing decision: path=%s, confidence=%.2f, escalated=%s",
            decision.path,
            decision.confidence,
            decision.escalated,
        )

        if decision.needs_clarification:
            return ContextPackage(
                session_id="clarify",
                intent="clarification",
                domain="general",
                context=[],
                tokens_used=0,
                tokens_retrieved=0,
                token_allocation={},
                score_summary=[],
                conflicts=[],
                warnings=[],
                needs_clarification=True,
                suggested_interpretations=decision.suggested_interpretations,
            )

        if decision.path == PathType.FAST:
            return await self._execute_fast_path(task, project_id, user_id, decision)
        elif decision.path == PathType.MEDIUM:
            return await self._execute_medium_path(
                task, project_id, user_id, role, max_tokens, decision, event_sink
            )
        else:
            return await self._execute_deep_path(
                task,
                project_id,
                user_id,
                role,
                max_tokens,
                trace_session_id,
                decision,
                event_sink,
            )

    async def _execute_fast_path(
        self, task: str, project_id: str | None, user_id: str | None, decision
    ) -> ContextPackage:
        """Fast path: Memory + Knowledge + Goals only. ~100ms."""
        ws = project_id or "default"
        context_items = []
        try:
            recent = await get_workspace_memory().get_recent(ws, limit=5)
            if recent:
                content = "Recent activity:\n" + "\n".join(
                    f"- {r.get('summary', '')}" for r in recent if r.get("summary")
                )
                context_items.append(
                    ContextItem(
                        source="workspace_memory",
                        query_type="recent",
                        content=content,
                        metadata={},
                        score=1.0,
                    )
                )
        except Exception:
            pass
        try:
            knowledge = await get_workspace_knowledge().search(
                ws, task, min_confidence=0.5, limit=3
            )
            if knowledge:
                content = "Relevant knowledge:\n" + "\n".join(
                    f"- [{k.get('knowledge_type','')}] {k.get('summary','')}"
                    for k in knowledge
                )
                context_items.append(
                    ContextItem(
                        source="workspace_knowledge",
                        query_type="search",
                        content=content,
                        metadata={},
                        score=0.9,
                    )
                )
        except Exception:
            pass
        try:
            goals = await get_goal_engine().get_active(ws, limit=5)
            if goals:
                content = "Active goals:\n" + "\n".join(
                    f"- {g['name']} ({g.get('progress',0):.0f}%)" for g in goals
                )
                context_items.append(
                    ContextItem(
                        source="workspace_goals",
                        query_type="active",
                        content=content,
                        metadata={},
                        score=0.8,
                    )
                )
        except Exception:
            pass
        tokens_used = sum(len((c.content or "").split()) for c in context_items)
        pkg = ContextPackage(
            session_id=str(uuid4()),
            intent="recall",
            domain="general",
            context=context_items,
            tokens_used=tokens_used,
            tokens_retrieved=0,
            token_allocation={},
            score_summary=[],
            conflicts=[],
            warnings=[],
        )
        return await self._ensure_human_readable(pkg)

    async def _execute_medium_path(
        self,
        task: str,
        project_id: str | None,
        user_id: str | None,
        role: str,
        max_tokens: int,
        decision,
        event_sink=None,
    ) -> ContextPackage:
        """Medium path: RIP search + Memory + Knowledge. ~2-5s."""
        classification = await self.classifier.classify_async(task)
        plan = self.planner.plan_medium(
            classification, task, max_tokens, project_id=project_id
        )
        execution_result = await self.executor.execute(plan, event_sink=event_sink)
        successful = [r for r in execution_result.source_responses if r.success]
        tagger = get_provenance_tagger()
        for r in successful:
            r.content = tagger.tag_and_wrap(r.source, r.content)
        ranked = await self.ranker.rank_and_compress(
            execution_result.source_responses, classification, task, max_tokens
        )
        context_items = [
            ContextItem(
                source=item.source,
                query_type=item.query_type,
                content=item.content,
                metadata=item.metadata,
                score=item.score,
            )
            for item in ranked.included
        ]
        warnings = [
            f"{r.source}: {r.error}"
            for r in execution_result.source_responses
            if not r.success
        ]
        tokens_retrieved = sum(r.token_count for r in successful)
        pkg = ContextPackage(
            session_id=str(uuid4()),
            intent=classification.intent.value,
            domain=classification.domain,
            context=context_items,
            tokens_used=ranked.tokens_used,
            tokens_retrieved=tokens_retrieved,
            token_allocation=plan.token_allocation,
            score_summary=[],
            conflicts=[],
            warnings=warnings,
        )
        return await self._ensure_human_readable(pkg)

    async def _execute_deep_path(
        self,
        task: str,
        project_id: str | None,
        user_id: str | None,
        role: str,
        max_tokens: int,
        trace_session_id: str | None,
        decision,
        event_sink=None,
    ) -> ContextPackage:
        """Deep path: Full pipeline with streaming, provenance, and security scanning."""
        logger.info("Starting DEEP path pipeline")
        classification = await self.classifier.classify_async(task)
        session = await self.session_store.create_session(
            agent_type="mcp_agent", task=task, classification=classification
        )
        session_id = str(session.id)

        async def emit(event):
            if event_sink:
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

        await emit(
            {
                "stage": "intent",
                "status": "done",
                "detail": f"{classification.intent.value} - {classification.domain} - DEEP path",
                "meta": {
                    "intent": classification.intent.value,
                    "domain": classification.domain,
                    "confidence": classification.confidence,
                },
            }
        )

        plan = self.planner.plan_deep(
            classification, task, max_tokens, project_id=project_id, role=role
        )
        await emit(
            {
                "stage": "plan",
                "status": "done",
                "detail": f"DEEP plan: {len(plan.steps)} steps, {max_tokens} tokens",
                "meta": {
                    "sources": list(plan.token_allocation),
                    "token_budget": max_tokens,
                },
            }
        )

        execution_result = await self.executor.execute(plan, event_sink=emit)
        successful = [r for r in execution_result.source_responses if r.success]

        tagger = get_provenance_tagger()
        scanner = get_injection_scanner()
        raw_items = [
            {
                "source": r.source,
                "query_type": r.query_type,
                "content": r.content,
                "metadata": r.metadata,
            }
            for r in successful
        ]
        tagged_raw = tagger.tag_all(raw_items)
        clean_items, flagged_items = scanner.scan_all(tagged_raw)
        if flagged_items:
            logger.warning(
                "DEEP path: %d items flagged by injection scanner", len(flagged_items)
            )

        for i, item in enumerate(clean_items):
            if i < len(successful):
                successful[i].content = item.get("content", successful[i].content)

        files_accessed = self._extract_files_from_responses(
            execution_result.source_responses
        )
        await self.session_store.update_files_accessed(session.id, files_accessed)

        conflicts = await self.conflict_detector.detect(session.id, files_accessed)
        if conflicts:
            await emit(
                {
                    "stage": "conflict_found",
                    "status": "done",
                    "detail": self._conflict_detail(conflicts),
                    "meta": {"count": len(conflicts)},
                }
            )

        ranked = await self.ranker.rank_and_compress(
            execution_result.source_responses, classification, task, max_tokens
        )
        await emit(
            {
                "stage": "compress",
                "status": "done",
                "detail": f"Compressed to {ranked.tokens_used} of {ranked.token_budget} tokens",
                "meta": {
                    "before": sum(r.token_count for r in successful),
                    "after": ranked.tokens_used,
                },
            }
        )

        user_role = self._coerce_role(role)
        filtered = await self.permissions.filter_context(
            ranked.included, user_role, classification.domain, session_id=session_id
        )

        context_items = [
            ContextItem(
                source=item.source,
                query_type=item.query_type,
                content=item.content,
                metadata=item.metadata,
                score=item.score,
            )
            for item in filtered
        ]
        warnings = self._build_warnings(execution_result.source_responses)
        tokens_retrieved = sum(
            r.token_count for r in execution_result.source_responses
        )
        await self.session_store.update_session_stats(
            session.id,
            sources_used=[r.source for r in execution_result.source_responses],
            tokens_retrieved=tokens_retrieved,
            tokens_delivered=ranked.tokens_used,
        )
        await emit(
            {
                "stage": "done",
                "status": "done",
                "detail": "DEEP path complete",
                "meta": {
                    "context_items": len(context_items),
                    "tokens_used": ranked.tokens_used,
                },
            }
        )

        pkg = ContextPackage(
            session_id=session_id,
            intent=classification.intent.value,
            domain=classification.domain,
            context=context_items,
            tokens_used=ranked.tokens_used,
            tokens_retrieved=tokens_retrieved,
            token_allocation=plan.token_allocation,
            score_summary=self._score_summary(ranked.included),
            conflicts=[c.model_dump(mode="json") for c in conflicts],
            warnings=warnings,
        )
        return await self._ensure_human_readable(pkg)

    def _coerce_role(self, role: str) -> UserRole:
        """Use configured default role if the caller sends an unknown value."""
        try:
            return UserRole(role)
        except ValueError:
            logger.warning("Unknown role supplied, using default", role=role)
            return UserRole(settings.default_role)

    def _extract_files_from_responses(
        self, responses: list[SourceResponse]
    ) -> list[str]:
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

    async def _ensure_human_readable(self, package: ContextPackage) -> ContextPackage:
        """Ensure all context texts in response package are human readable.
        If non-human-readable content is detected, reformat/rewrite it using the currently configured LLM.
        """
        if not package or not package.context:
            return package

        for item in package.context:
            if item.content and not self._is_human_readable(item.content):
                logger.info(
                    "Non-human-readable content detected in response context; converting using configured LLM",
                    source=item.source,
                )
                item.content = await self._make_human_readable_with_llm(item.content)

        return package

    def _is_human_readable(self, text: str) -> bool:
        """Check if content string is human readable."""
        if not text or not text.strip():
            return True

        # Check null bytes or control character ratio
        control_chars = sum(
            1 for c in text if not c.isprintable() and c not in "\n\r\t"
        )
        if control_chars / len(text) > 0.03:
            return False

        # Check unicode replacement characters (corrupted encoding)
        if text.count("\ufffd") > 2:
            return False

        # Check raw hex/binary escape sequences like \x80\x91...
        hex_escapes = len(re.findall(r"\\x[0-9a-fA-F]{2}", text))
        if hex_escapes > 3:
            return False

        # Check for exceptionally long continuous non-space tokens (e.g. raw base64 / binary dumps)
        words = text.split()
        if words and len(text) > 100:
            max_word_len = max(len(w) for w in words)
            if max_word_len > 150:
                return False

        return True

    async def _make_human_readable_with_llm(self, text: str) -> str:
        """Use currently configured LLM to convert non-human-readable text into clean human-readable text."""
        prompt = (
            "The following text or data in context response is not easily human readable "
            "(it may contain raw binary dumps, corrupted characters, escaped sequences, or unformatted data).\n"
            "Please convert and reformat it into clean, readable, clear human text. "
            "Preserve all relevant technical facts and structure.\n\n"
            f"Raw Content:\n{text[:4000]}"
        )
        try:
            from gateway.core.llm_pool.router import get_llm_router

            llm_router = get_llm_router()
            config = await llm_router.get_config()
            formatted = await llm_router.query_llm(
                prompt=prompt,
                config=config,
                system_prompt="You are an expert assistant that converts raw, corrupted, binary, or obscure text into clean, readable human text.",
                max_tokens=1500,
                temperature=0.1,
            )
            if formatted and formatted.strip():
                return formatted.strip()
        except Exception as exc:
            logger.warning("Failed to process text using configured LLM: %s", exc)

        # Fallback cleanup if LLM is unavailable
        cleaned = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
        cleaned = re.sub(r"\\x[0-9a-fA-F]{2}", "", cleaned)
        return cleaned.strip()


# Global pipeline instance
_pipeline: GatewayPipeline | None = None


def get_context_pipeline() -> GatewayPipeline:
    """Get the global context pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = GatewayPipeline()
    return _pipeline