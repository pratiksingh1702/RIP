"""Audit log storage."""

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.permissions.models import UserRole
from gateway.storage.database import async_session_factory
from gateway.storage.models import AuditLog

logger = structlog.get_logger(__name__)


class AuditStore:
    """Store for managing audit logs."""

    def __init__(self, db_session: AsyncSession | None = None):
        self._db_session = db_session

    async def _get_db(self) -> AsyncSession:
        if self._db_session:
            return self._db_session
        return async_session_factory()

    async def _close_if_owned(self, db: AsyncSession) -> None:
        if self._db_session is None:
            await db.close()

    async def log_access(
        self,
        session_id: str,
        role: UserRole,
        action: str,
        allowed: bool,
        user_id: str | None = None,
        source: str | None = None,
        reason: str | None = None
    ) -> None:
        """Create a new audit log entry."""
        db = await self._get_db()
        try:
            log_entry = AuditLog(
                id=uuid4(),
                timestamp=datetime.now(UTC),
                session_id=session_id,
                user_id=user_id,
                role=role.value,
                action=action,
                source=source,
                allowed=allowed,
                reason=reason
            )
            db.add(log_entry)
            await db.commit()
        except Exception as e:
            logger.error("Failed to save audit log", error=str(e))
            await db.rollback()
        finally:
            await self._close_if_owned(db)

    async def list_logs(
        self,
        *,
        session_id: str | None = None,
        role: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List recent audit logs with lightweight filters."""
        db = await self._get_db()
        try:
            query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
            if session_id:
                query = query.where(AuditLog.session_id == session_id)
            if role:
                query = query.where(AuditLog.role == role)
            result = await db.execute(query)
            return list(result.scalars().all())
        finally:
            await self._close_if_owned(db)


# Global store instance
_audit_store: AuditStore | None = None


def get_audit_store() -> AuditStore:
    """Get the global audit store instance."""
    global _audit_store
    if _audit_store is None:
        _audit_store = AuditStore()
    return _audit_store
