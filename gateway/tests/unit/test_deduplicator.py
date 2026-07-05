"""Unit tests for deduplicator."""


from gateway.core.ranker.deduplicator import Deduplicator
from gateway.core.ranker.models import ScoredItem


def test_deduplicator_initialization():
    """Test that deduplicator initializes correctly."""
    deduplicator = Deduplicator()
    assert deduplicator is not None


def test_deduplicate_removes_duplicates():
    """Test that deduplicator removes exact duplicates."""
    deduplicator = Deduplicator()
    items = [
        ScoredItem(
            source="rip",
            query_type="search",
            content="Same content here",
            metadata={},
            score=0.8
        ),
        ScoredItem(
            source="rip",
            query_type="search",
            content="Same content here",
            metadata={},
            score=0.7
        )
    ]
    result = deduplicator.deduplicate(items)
    assert len(result) == 1
    assert result[0].score == 0.8  # Keeps higher score


def test_deduplicate_keeps_unique():
    """Test that deduplicator keeps unique items."""
    deduplicator = Deduplicator()
    items = [
        ScoredItem(
            source="rip",
            query_type="search",
            content="Content 1",
            metadata={},
            score=0.8
        ),
        ScoredItem(
            source="rip",
            query_type="search",
            content="Content 2",
            metadata={},
            score=0.7
        )
    ]
    result = deduplicator.deduplicate(items)
    assert len(result) == 2
