"""Session store backed by database."""

from datetime import datetime
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

    async def create_session(
        self,
        agent_type: str,
        task: str,
        classification: ClassificationResult
    ) -> Session:
        """Create a new session."""
        db = await self._get_db()
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

        return Session(
            id=db_session.id,
            agent_type=db_session.agent_type,
            task_description=db_session.task_description,
            classification=classification,
            files_accessed=db_session.files_accessed or [],
            nodes_accessed=db_session.nodes_accessed or [],
            sources_used=db_session.sources_used or [],
            tokens_retrieved=db_session.tokens_retrieved or 0,
            tokens_delivered=db_session.tokens_delivered or 0,
            tokens_saved=db_session.tokens_saved or 0,
            status=db_session.status,
            outcome=db_session.outcome,
            files_modified=db_session.files_modified or [],
            started_at=db_session.started_at,
            ended_at=db_session.ended_at,
            git_branch=db_session.git_branch,
            project_id=db_session.project_id,
            user_id=db_session.user_id
        )

    async def update_files_accessed(
        self,
        session_id: UUID,
        files: List[str]
    ) -> None:
        """Update files accessed by session."""
        db = await self._get_db()
        result = await db.execute(select(DbSession).where(DbSession.id == session_id))
        db_session = result.scalar_one_or_none()

        if db_session:
            current = db_session.files_accessed or []
            db_session.files_accessed = list(set(current + files))
            await db.commit()

    async def complete_session(
        self,
        session_id: UUID,
        outcome: str,
        files_modified: List[str]
    ) -> None:
        """Mark session as complete."""
        db = await self._get_db()
        result = await db.execute(select(DbSession).where(DbSession.id == session_id))
        db_session = result.scalar_one_or_none()

        if db_session:
            db_session.status = "completed"
            db_session.outcome = outcome
            db_session.files_modified = files_modified
            db_session.ended_at = datetime.utcnow()
            await db.commit()

    async def get_active_sessions(
        self,
        exclude_session_id: Optional[UUID] = None
    ) -> List[Session]:
        """Get all in-progress sessions."""
        db = await self._get_db()
        query = select(DbSession).where(DbSession.status == "in_progress")

        if exclude_session_id:
            query = query.where(DbSession.id != exclude_session_id)

        result = await db.execute(query)
        db_sessions = result.scalars().all()

        sessions = []
        for db_sess in db_sessions:
            sessions.append(
                Session(
                    id=db_sess.id,
                    agent_type=db_sess.agent_type,
                    task_description=db_sess.task_description,
                    classification=ClassificationResult(
                        intent=db_sess.intent,
                        confidence=0.9,  # placeholder
                        domain=db_sess.domain or "general",
                        risk_level=db_sess.risk_level,
                        strategy="rules",
                        domain_keywords_found=[],
                        raw_task=db_sess.task_description
                    ),
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
                    user_id=db_sess.user_id
                )
            )
        return sessions

    async def get_recent_sessions(
        self,
        domain: str,
        hours: int = 24
    ) -> List[Session]:
        """Get recent sessions for a domain."""
        db = await self._get_db()
        cutoff = datetime.utcnow() - datetime.timedelta(hours=hours)
        query = select(DbSession).where(
            DbSession.domain == domain,
            DbSession.ended_at >= cutoff
        ).order_by(DbSession.ended_at.desc())

        result = await db.execute(query)
        db_sessions = result.scalars().all()

        sessions = []
        for db_sess in db_sessions:
            sessions.append(
                Session(
                    id=db_sess.id,
                    agent_type=db_sess.agent_type,
                    task_description=db_sess.task_description,
                    classification=ClassificationResult(
                        intent=db_sess.intent,
                        confidence=0.9,
                        domain=db_sess.domain or "general",
                        risk_level=db_sess.risk_level,
                        strategy="rules",
                        domain_keywords_found=[],
                        raw_task=db_sess.task_description
                    ),
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
                    user_id=db_sess.user_id
                )
            )
        return sessions


# Global store instance
_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get the global session store."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
