"""Session store backed by database."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.classifier.models import ClassificationResult
from gateway.storage.database import async_session_factory
from gateway.storage.models import Session as DbSession
from .models import Session

logger = structlog.get_logger(__name__)


class SessionStore:
    """Store for managing sessions."""

    def __init__(self, db_session: AsyncSession | None = None):
        self._db_session = db_session

    async def _get_db(self) -> AsyncSession:
        """Get a database session."""
        if self._db_session:
            return self._db_session
        return async_session_factory()

    async def _close_if_owned(self, db: AsyncSession) -> None:
        """Close sessions created by this store while preserving injected sessions."""
        if self._db_session is None:
            await db.close()

    async def create_session(
        self,
        agent_type: str,
        task: str,
        classification: ClassificationResult
    ) -> Session:
        """Create a new session."""
        db = await self._get_db()
        try:
            session_id = uuid4()

            db_session = DbSession(
                id=session_id,
                agent_type=agent_type,
                task_description=task,
                intent=classification.intent.value,
                domain=classification.domain,
                risk_level=classification.risk_level.value,
                started_at=datetime.utcnow()
            )

            db.add(db_session)
            await db.commit()
            await db.refresh(db_session)

            return self._to_session(db_session, classification)
        finally:
            await self._close_if_owned(db)

    async def update_files_accessed(
        self,
        session_id: UUID,
        files: List[str]
    ) -> None:
        """Update files accessed by session."""
        db = await self._get_db()
        try:
            result = await db.execute(select(DbSession).where(DbSession.id == session_id))
            db_session = result.scalar_one_or_none()

            if db_session:
                current = db_session.files_accessed or []
                db_session.files_accessed = sorted(set(current + files))
                await db.commit()
        finally:
            await self._close_if_owned(db)

    async def update_session_stats(
        self,
        session_id: UUID,
        *,
        sources_used: List[str],
        tokens_retrieved: int,
        tokens_delivered: int,
    ) -> None:
        """Update source and token counters for a session."""
        db = await self._get_db()
        try:
            result = await db.execute(select(DbSession).where(DbSession.id == session_id))
            db_session = result.scalar_one_or_none()

            if db_session:
                db_session.sources_used = sorted(set(sources_used))
                db_session.tokens_retrieved = tokens_retrieved
                db_session.tokens_delivered = tokens_delivered
                db_session.tokens_saved = max(0, tokens_retrieved - tokens_delivered)
                await db.commit()
        finally:
            await self._close_if_owned(db)

    async def complete_session(
        self,
        session_id: UUID,
        outcome: str,
        files_modified: List[str]
    ) -> None:
        """Mark session as complete."""
        db = await self._get_db()
        try:
            result = await db.execute(select(DbSession).where(DbSession.id == session_id))
            db_session = result.scalar_one_or_none()

            if db_session:
                db_session.status = "completed"
                db_session.outcome = outcome
                db_session.files_modified = files_modified
                db_session.ended_at = datetime.utcnow()
                await db.commit()
        finally:
            await self._close_if_owned(db)

    async def get_active_sessions(
        self,
        exclude_session_id: Optional[UUID] = None
    ) -> List[Session]:
        """Get all in-progress sessions."""
        db = await self._get_db()
        query = select(DbSession).where(DbSession.status == "in_progress")

        if exclude_session_id:
            query = query.where(DbSession.id != exclude_session_id)

        try:
            result = await db.execute(query)
            db_sessions = result.scalars().all()
            return [self._to_session(db_sess) for db_sess in db_sessions]
        finally:
            await self._close_if_owned(db)

    async def get_recent_sessions(
        self,
        domain: str,
        hours: int = 24
    ) -> List[Session]:
        """Get recent sessions for a domain."""
        db = await self._get_db()
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = select(DbSession).where(
            DbSession.domain == domain,
            DbSession.ended_at >= cutoff
        ).order_by(DbSession.ended_at.desc())

        try:
            result = await db.execute(query)
            db_sessions = result.scalars().all()
            return [self._to_session(db_sess) for db_sess in db_sessions]
        finally:
            await self._close_if_owned(db)

    def _to_session(
        self,
        db_sess: DbSession,
        classification: ClassificationResult | None = None,
    ) -> Session:
        """Convert ORM session rows to gateway memory models."""
        classification = classification or ClassificationResult(
            intent=db_sess.intent,
            confidence=0.9,
            domain=db_sess.domain or "general",
            risk_level=db_sess.risk_level,
            strategy="rules",
            domain_keywords_found=[],
            raw_task=db_sess.task_description,
        )
        return Session(
            id=db_sess.id,
            agent_type=db_sess.agent_type,
            task_description=db_sess.task_description,
            classification=classification,
            files_accessed=db_sess.files_accessed or [],
            nodes_accessed=db_sess.nodes_accessed or [],
            sources_used=db_sess.sources_used or [],
            tokens_retrieved=db_sess.tokens_retrieved or 0,
            tokens_delivered=db_sess.tokens_delivered or 0,
            tokens_saved=db_sess.tokens_saved or 0,
            status=db_sess.status,
            outcome=db_sess.outcome,
            files_modified=db_sess.files_modified or [],
            started_at=db_sess.started_at,
            ended_at=db_sess.ended_at,
            git_branch=db_sess.git_branch,
            project_id=db_sess.project_id,
            user_id=db_sess.user_id,
        )


# Global store instance
_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get the global session store."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
