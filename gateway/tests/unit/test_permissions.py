"""Unit tests for permissions."""

from gateway.core.permissions import PermissionEngine, UserRole
from gateway.core.ranker.models import ScoredItem


def test_permission_engine_initialization():
    """Test permission engine initializes correctly."""
    engine = PermissionEngine()
    assert engine is not None
    assert len(engine.policies) > 0


def test_get_policy():
    """Test getting policy for each role."""
    engine = PermissionEngine()
    for role in UserRole:
        policy = engine.get_policy(role)
        assert policy is not None
        assert policy.role == role


def test_junior_dev_cannot_access_sensitive_domain():
    """Test junior dev cannot access sensitive domain content."""
    engine = PermissionEngine()
    items = [
        ScoredItem(
            source="rip",
            query_type="search",
            content="Payment processing code",
            metadata={},
            score=0.9
        )
    ]
    filtered = engine.filter_context(
        items,
        UserRole.JUNIOR_DEV,
        domain="payment"
    )
    assert len(filtered) == 0


def test_developer_can_access_sensitive_domain():
    """Test developer can access sensitive domain content."""
    engine = PermissionEngine()
    items = [
        ScoredItem(
            source="rip",
            query_type="search",
            content="Payment processing code",
            metadata={},
            score=0.9
        )
    ]
    filtered = engine.filter_context(
        items,
        UserRole.DEVELOPER,
        domain="payment"
    )
    assert len(filtered) == 1


def test_senior_dev_full_access():
    """Test senior dev has full access."""
    engine = PermissionEngine()
    items = [
        ScoredItem(
            source="rip",
            query_type="search",
            content="Auth code",
            metadata={},
            score=0.9
        )
    ]
    filtered = engine.filter_context(
        items,
        UserRole.SENIOR_DEV,
        domain="auth"
    )
    assert len(filtered) == 1


def test_audit_log_created():
    """Test that audit logs are created when filtering."""
    engine = PermissionEngine()
    items = [
        ScoredItem(
            source="rip",
            query_type="search",
            content="Test content",
            metadata={},
            score=0.9
        )
    ]
    engine.filter_context(
        items,
        UserRole.DEVELOPER,
        domain="general",
        session_id="test-session-123"
    )
    assert len(engine.audit_log) >= 1
    assert engine.audit_log[0].session_id == "test-session-123"
