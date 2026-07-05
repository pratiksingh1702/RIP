"""Tests for the planner engine."""


from gateway.core.classifier.models import ClassificationResult, IntentType, RiskLevel
from gateway.core.planner.engine import plan


def test_planner_bug_fix_plan():
    """Test that bug fix plans prioritize RIP trace."""
    classification = ClassificationResult(
        intent=IntentType.BUG_FIX,
        confidence=0.9,
        domain="payment",
        risk_level=RiskLevel.HIGH,
        strategy="rules",
        domain_keywords_found=["payment"],
        raw_task="Fix payment null pointer"
    )

    p = plan(classification, "Fix payment null pointer", max_tokens=12000)

    assert p.classification.intent == IntentType.BUG_FIX
    assert any(q.query_type == "trace" for step in p.steps for q in step.queries)
    assert any(q.query_type == "search" for step in p.steps for q in step.queries)


def test_planner_architecture_question_plan():
    """Test architecture question plan structure."""
    classification = ClassificationResult(
        intent=IntentType.ARCHITECTURAL_QUESTION,
        confidence=0.9,
        domain="api",
        risk_level=RiskLevel.LOW,
        strategy="rules",
        domain_keywords_found=["api"],
        raw_task="How does the API work?"
    )

    p = plan(classification, "How does the API work?", max_tokens=12000)

    assert p.classification.intent == IntentType.ARCHITECTURAL_QUESTION
    assert any(q.query_type == "architecture" for step in p.steps for q in step.queries)


def test_planner_token_allocation():
    """Test token budget allocation."""
    classification = ClassificationResult(
        intent=IntentType.FEATURE_ADDITION,
        confidence=0.9,
        domain="payment",
        risk_level=RiskLevel.MEDIUM,
        strategy="rules",
        domain_keywords_found=["payment"],
        raw_task="Add retry logic to payments"
    )

    p = plan(classification, "Add retry logic to payments", max_tokens=12000)

    assert "rip" in p.token_allocation
    assert p.token_allocation["rip"] > 0
