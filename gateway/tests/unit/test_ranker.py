"""Unit tests for ranker."""

import pytest
from datetime import datetime

from gateway.core.classifier.models import ClassificationResult, IntentType, RiskLevel
from gateway.core.ranker.engine import RankerEngine
from gateway.core.ranker.models import ScoredItem
from gateway.core.sources.models import SourceResponse


def test_ranker_initialization():
    """Test that ranker initializes correctly."""
    engine = RankerEngine()
    assert engine is not None
    assert engine.pattern_scorer is not None
    assert engine.recency_scorer is not None
    assert engine.authority_scorer is not None
    assert engine.deduplicator is not None
    assert engine.compressor is not None


def test_pattern_scorer():
    """Test pattern scorer."""
    engine = RankerEngine()
    score = engine.pattern_scorer.score(
        "Fix payment null pointer",
        "Payment service has null check for pointer"
    )
    assert score > 0


def test_authority_scorer():
    """Test authority scorer."""
    engine = RankerEngine()
    score1 = engine.authority_scorer.score("rip", "trace")
    score2 = engine.authority_scorer.score("slack", "search")
    assert score1 > score2


@pytest.mark.asyncio
async def test_rank_and_compress():
    """Test rank and compress with mock responses."""
    engine = RankerEngine()
    classification = ClassificationResult(
        intent=IntentType.BUG_FIX,
        confidence=0.9,
        domain="payment",
        risk_level=RiskLevel.HIGH,
        strategy="rules",
        domain_keywords_found=["payment"],
        raw_task="Fix payment null pointer"
    )
    responses = [
        SourceResponse(
            source="rip",
            query_type="trace",
            content="Payment processing flow trace here",
            metadata={},
            token_count=50,
            latency_ms=100,
            success=True
        ),
        SourceResponse(
            source="rip",
            query_type="search",
            content="Similar error handling patterns found",
            metadata={},
            token_count=40,
            latency_ms=150,
            success=True
        )
    ]
    result = await engine.rank_and_compress(responses, classification, "Fix payment null pointer", 200)
    assert result is not None
    assert len(result.included) > 0
    assert result.tokens_used <= 200
