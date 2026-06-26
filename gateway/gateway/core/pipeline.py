"""End-to-end pipeline orchestrator (Phase 10)."""

import structlog
from typing import List
from uuid import uuid4
from datetime import datetime

from gateway.config import settings
from gateway.core.classifier.engine import ClassifierEngine
from gateway.core.planner.engine import PlannerEngine
from gateway.core.executor.engine import ExecutorEngine
from gateway.core.ranker.engine import RankerEngine
from gateway.core.permissions import PermissionEngine, UserRole
from gateway.core.memory.store import SessionStore, Session
from gateway.core.memory.conflict_detector import ConflictDetector
from gateway.core.sources.registry import get_source_registry
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
        session_id = str(uuid4())
        logger.info("Starting context pipeline", session_id=session_id, task=task[:50])

        # Step 1: Classify intent
        classification = self.classifier.classify(task)
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

        # Step 5: Rank and compress
        ranked = await self.ranker.rank_and_compress(
            execution_result.source_responses,
            classification,
            task,
            max_tokens
        )

        # Step 6: Apply permissions
        user_role = UserRole(role)
        filtered = self.permissions.filter_context(
            ranked.included,
            user_role,
            classification.domain,
            session_id=session_id
        )

        # Step 7: Detect conflicts
        conflicts = []
        active_sessions = await self.session_store.get_active_sessions(exclude_session_id=session.id)
        if active_sessions:
            # For now, we don't have file access data, so skip conflict detection
            pass

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

        # Update session
        await self.session_store.update_files_accessed(
            session.id,
            []  # TODO: Extract actual files from source responses
        )

        logger.info(
            "Pipeline complete",
            session_id=session_id,
            context_items=len(context_items),
            tokens_used=ranked.tokens_used
        )

        return ContextPackage(
            session_id=session_id,
            intent=classification.intent,
            domain=classification.domain,
            context=context_items,
            tokens_used=ranked.tokens_used,
            conflicts=conflicts,
            warnings=[]
        )
