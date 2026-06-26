"""Unit tests for intent classifier."""

import os
import sys

# Add gateway directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from gateway.core.classifier.engine import classify
from gateway.core.classifier.models import IntentType


def test_bug_fix_classification():
    result = classify("Fix the null pointer in payment flow")
    print(f"\nTest Bug Fix: intent={result.intent}, domain={result.domain}, domain_keywords={result.domain_keywords_found}")
    assert result.intent == IntentType.BUG_FIX


def test_feature_addition_classification():
    result = classify("Add retry logic to Stripe integration")
    print(f"\nTest Feature Addition: intent={result.intent}, domain={result.domain}, domain_keywords={result.domain_keywords_found}")
    assert result.intent == IntentType.FEATURE_ADDITION


def test_architectural_question_classification():
    result = classify("How does authentication work?")
    print(f"\nTest Architectural Question: intent={result.intent}, domain={result.domain}, domain_keywords={result.domain_keywords_found}")
    assert result.intent == IntentType.ARCHITECTURAL_QUESTION


def test_refactor_classification():
    result = classify("Refactor UserService to use repository pattern")
    print(f"\nTest Refactor: intent={result.intent}, domain={result.domain}, domain_keywords={result.domain_keywords_found}")
    assert result.intent == IntentType.REFACTOR


if __name__ == "__main__":
    print("Running Context Gateway Classifier Tests...")
    test_bug_fix_classification()
    test_feature_addition_classification()
    test_architectural_question_classification()
    test_refactor_classification()
    print("\n✅ All tests passed!")
