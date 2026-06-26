"""Unit tests for executor."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from gateway.core.classifier.models import ClassificationResult, IntentType, RiskLevel
from gateway.core.planner.models import Plan, RetrievalStep, SourceQuery
from gateway.core.executor.engine import ExecutorEngine
from gateway.core.sources.models import SourceResponse


def test_executor_initialization():
    """Test that executor initializes correctly."""
    engine = ExecutorEngine()
    assert engine is not None
    assert engine.source_registry is not None
    assert engine.circuit_breaker is not None


@pytest.mark.asyncio
async def test_execute_plan_empty():
    """Test executing an empty plan."""
    engine = ExecutorEngine()
    classification = ClassificationResult(
        intent=IntentType.BUG_FIX,
        confidence=0.9,
        domain="payment",
        risk_level=RiskLevel.HIGH,
        strategy="rules",
        domain_keywords_found=["payment"],
        raw_task="Fix bug"
    )
    plan = Plan(
        classification=classification,
        steps=[],
        token_budget=12000,
        token_allocation={"rip": 12000},
        estimated_tokens_raw=0,
        created_at=datetime.utcnow()
    )
    
    result = await engine.execute(plan)
    assert result is not None
    assert len(result.source_responses) == 0
    assert result.success_count == 0
    assert result.failure_count == 0
