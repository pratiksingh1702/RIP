"""Unit tests for compressor."""

import pytest

from gateway.core.ranker.compressor import ContextCompressor
from gateway.core.ranker.models import ScoredItem


def test_compressor_initialization():
    """Test that compressor initializes correctly."""
    compressor = ContextCompressor()
    assert compressor is not None
    assert compressor.token_counter is not None


@pytest.mark.asyncio
async def test_compress_fits_budget():
    """Test that compressed content fits within token budget."""
    compressor = ContextCompressor()
    items = [
        ScoredItem(
            source="rip",
            query_type="search",
            content="A" * 100,
            metadata={},
            score=0.9
        ),
        ScoredItem(
            source="rip",
            query_type="search",
            content="B" * 100,
            metadata={},
            score=0.8
        ),
        ScoredItem(
            source="rip",
            query_type="search",
            content="C" * 100,
            metadata={},
            score=0.7
        )
    ]
    result = await compressor.compress(items, 100)
    assert result.tokens_used <= 100


@pytest.mark.asyncio
async def test_compress_prioritizes_higher_score():
    """Test that higher scored items are included first."""
    compressor = ContextCompressor()
    items = [
        ScoredItem(
            source="rip",
            query_type="search",
            content="Low score content",
            metadata={},
            score=0.3
        ),
        ScoredItem(
            source="rip",
            query_type="search",
            content="High score content",
            metadata={},
            score=0.9
        )
    ]
    result = await compressor.compress(items, 100)
    assert len(result.included) >= 1
    assert result.included[0].score > result.included[-1].score if len(result.included) > 1 else True
