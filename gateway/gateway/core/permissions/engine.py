"""Permission engine for filtering context."""

import structlog
from datetime import datetime
from typing import List

from .models import UserRole, AccessPolicy, AuditLogEntry
from .roles import DEFAULT_POLICIES, SENSITIVE_DOMAINS
from gateway.core.ranker.models import ScoredItem
from gateway.storage.audit_store import get_audit_store

logger = structlog.get_logger(__name__)


class PermissionEngine:
    """Engine to filter context based on user role."""

    def __init__(self):
        self.policies = DEFAULT_POLICIES
        self.audit_store = get_audit_store()

    def get_policy(self, role: UserRole) -> AccessPolicy:
        """Get access policy for a role."""
        return self.policies.get(role, self.policies[UserRole.DEVELOPER])

    async def filter_context(
        self,
        items: List[ScoredItem],
        role: UserRole,
        domain: str | None = None,
        session_id: str = "unknown",
        user_id: str | None = None
    ) -> List[ScoredItem]:
        """Filter items based on role permissions."""
        policy = self.get_policy(role)
        filtered: List[ScoredItem] = []

        for item in items:
            # Check if source is allowed
            source_allowed = "*" in policy.allowed_sources or item.source in policy.allowed_sources
            # Check if domain is sensitive
            domain_sensitive = domain in SENSITIVE_DOMAINS if domain else False
            domain_allowed = policy.can_access_sensitive_domains or not domain_sensitive

            allowed = source_allowed and domain_allowed

            # Log audit entry
            reason = ""
            if not source_allowed:
                reason = f"Source {item.source} not allowed for role {role}"
            elif not domain_allowed:
                reason = f"Domain {domain} is sensitive and role {role} cannot access it"

            await self._log_audit(
                session_id=session_id,
                user_id=user_id,
                role=role,
                action="filter_item",
                source=item.source,
                allowed=allowed,
                reason=reason if not allowed else None
            )

            if allowed:
                filtered.append(item)

        logger.info(
            "Context filtered",
            role=role,
            original_count=len(items),
            filtered_count=len(filtered)
        )
        return filtered

    async def _log_audit(
        self,
        session_id: str,
        user_id: str | None,
        role: UserRole,
        action: str,
        source: str | None,
        allowed: bool,
        reason: str | None
    ):
        """Log an audit entry to persistent storage."""
        await self.audit_store.log_access(
            session_id=session_id,
            user_id=user_id,
            role=role,
            action=action,
            source=source,
            allowed=allowed,
            reason=reason
        )
