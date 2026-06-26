"""Unit tests for memory components."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from gateway.core.classifier.models import ClassificationResult, IntentType, RiskLevel
from gateway.core.memory.store import SessionStore
from gateway.core.memory.conflict_detector import ConflictDetector
from gateway.core.memory.context_bridge import ContextBridge
from gateway.core.memory.models import Session, Conflict


def test_conflict_detector_initialization():
    """Test that conflict detector initializes correctly."""
    detector = ConflictDetector()
    assert detector is not None
    assert detector.store is not None


def test_context_bridge_initialization():
    """Test that context bridge initializes correctly."""
    bridge = ContextBridge()
    assert bridge is not None
    assert bridge.store is not None


def test_assess_conflict_risk_high():
    """Test high risk conflict assessment."""
    detector = ConflictDetector()
    # Test with payment file
    session = Session(
        id=uuid4(),
        agent_type="test",
        task_description="Test task",
        classification=ClassificationResult(
            intent=IntentType.BUG_FIX,
            confidence=0.9,
            domain="payment",
            risk_level=RiskLevel.HIGH,
            strategy="rules",
            domain_keywords_found=[],
            raw_task="Test"
        ),
        files_accessed=["payment_service.py"],
        nodes_accessed=[],
        sources_used=[],
        tokens_retrieved=0,
        tokens_delivered=0,
        tokens_saved=0,
        status="in_progress",
        outcome=None,
        files_modified=[],
        started_at=datetime.utcnow(),
        ended_at=None,
        git_branch=None,
        project_id=None,
        user_id=None
    )
    risk = detector._assess_conflict_risk(["payment_service.py"], session)
    assert risk == "high"


def test_assess_conflict_risk_medium():
    """Test medium risk conflict assessment."""
    detector = ConflictDetector()
    session = Session(
        id=uuid4(),
        agent_type="test",
        task_description="Test task",
        classification=ClassificationResult(
            intent=IntentType.BUG_FIX,
            confidence=0.9,
            domain="general",
            risk_level=RiskLevel.MEDIUM,
            strategy="rules",
            domain_keywords_found=[],
            raw_task="Test"
        ),
        files_accessed=["utils.py"],
        nodes_accessed=[],
        sources_used=[],
        tokens_retrieved=0,
        tokens_delivered=0,
        tokens_saved=0,
        status="in_progress",
        outcome=None,
        files_modified=[],
        started_at=datetime.utcnow(),
        ended_at=None,
        git_branch=None,
        project_id=None,
        user_id=None
    )
    risk = detector._assess_conflict_risk(["utils.py"], session)
    assert risk == "medium"
