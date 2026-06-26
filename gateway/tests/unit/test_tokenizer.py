"""Unit tests for tokenizer."""

import pytest
from gateway.core.tokenizer.counter import TokenCounter, get_token_counter


def test_token_counter_initialization():
    """Test that token counter initializes correctly."""
    counter = TokenCounter()
    assert counter is not None


def test_token_counter_count_empty():
    """Test counting empty string."""
    counter = TokenCounter()
    assert counter.count("") == 0


def test_token_counter_count_simple_text():
    """Test counting simple text."""
    counter = TokenCounter()
    count = counter.count("Hello, world!")
    assert count > 0


def test_get_token_counter_singleton():
    """Test that get_token_counter returns singleton."""
    counter1 = get_token_counter()
    counter2 = get_token_counter()
    assert counter1 is counter2
