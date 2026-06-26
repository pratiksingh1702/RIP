"""Unit tests for learning loop and LLM fallback."""

import pytest

from gateway.core.learning.feedback import FeedbackStore, get_feedback_store
from gateway.core.learning.scorer_weights import ScorerWeights, get_scorer_weights
from gateway.core.learning.llm_client import LLMClient, get_llm_client


def test_feedback_store():
    """Test feedback store initialization and adding feedback."""
    store = FeedbackStore()
    feedback = {"session_id": "test-123", "rating": 5, "comment": "great context"}
    assert len(store._feedback) == 0


def test_scorer_weights():
    """Test scorer weights initialization and getting weights."""
    weights = ScorerWeights()
    current = weights.get_weights()
    assert set(current.keys()) == set(ScorerWeights.DEFAULT_WEIGHTS.keys())
    assert sum(current.values()) == pytest.approx(1.0)


def test_llm_client():
    """Test LLM client initialization."""
    client = LLMClient()
    assert client is not None


def test_global_instances():
    """Test global instance functions return same instance."""
    store1 = get_feedback_store()
    store2 = get_feedback_store()
    assert store1 is store2

    weights1 = get_scorer_weights()
    weights2 = get_scorer_weights()
    assert weights1 is weights2

    client1 = get_llm_client()
    client2 = get_llm_client()
    assert client1 is client2
