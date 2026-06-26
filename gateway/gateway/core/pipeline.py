"""End-to-end pipeline orchestrator (Phase 10)."""

import re
import structlog

from gateway.config import settings
from gateway.core.classifier.engine import ClassifierEngine
from gateway.core.planner.engine import PlannerEngine
from gateway.core.executor.engine import ExecutorEngine
from gateway.core.ranker.engine import RankerEngine
from gateway.core.permissions import PermissionEngine, UserRole
from gateway.core.memory.store import SessionStore
from gateway.core.memory.conflict_detector import ConflictDetector
from gateway.core.sources.registry import get_source_registry
from gateway.core.sources.models import SourceResponse
from gateway.server.schemas.common import ContextPackage, ContextItem

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
        role: str = "developer"
    ) -> ContextPackage:
        """Run full pipeline to get context."""
        logger.info("Starting context pipeline", task=task[:50])

        # Step 1: Classify intent
        classification = await self.classifier.classify_async(task)
        logger.info(
            "Classification complete",
            intent=classification.intent,
            domain=classification.domain,
            confidence=classification.confidence
        )

        # Step 2: Create session
        session = await self.session_store.create_session(
            agent_type="mcp_agent",
            task=task,
            classification=classification
        )
        session_id = str(session.id)

        # Step 3: Plan retrieval
        plan = self.planner.plan(classification, task, max_tokens)
        logger.info("Plan created", steps=len(plan.steps))

        # Step 4: Execute retrieval
        execution_result = await self.executor.execute(plan)
        logger.info(
            "Execution complete",
            success_count=execution_result.success_count,
            failure_count=execution_result.failure_count,
            total_latency=execution_result.total_latency_ms
        )

        files_accessed = self._extract_files_from_responses(execution_result.source_responses)
        await self.session_store.update_files_accessed(session.id, files_accessed)

        # Step 5: Detect conflicts before final formatting so warnings are visible.
        conflicts = await self.conflict_detector.detect(session.id, files_accessed)

        # Step 6: Rank and compress
        ranked = await self.ranker.rank_and_compress(
            execution_result.source_responses,
            classification,
            task,
            max_tokens
        )

        # Step 7: Apply permissions
        user_role = self._coerce_role(role)
        filtered = await self.permissions.filter_context(
            ranked.included,
            user_role,
            classification.domain,
            session_id=session_id
        )

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

        logger.info(
            "Pipeline complete",
            session_id=session_id,
            context_items=len(context_items),
            tokens_used=ranked.tokens_used,
            conflicts=len(conflicts),
        )

        return ContextPackage(
            session_id=session_id,
            intent=classification.intent.value,
            domain=classification.domain,
            context=context_items,
            tokens_used=ranked.tokens_used,
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
            if not response.success and response.error:
                warnings.append(f"{response.source}/{response.query_type}: {response.error}")
        return warnings
