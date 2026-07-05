"""Debug the classifier."""
import sys

sys.path.insert(0, '.')

from gateway.core.classifier.models import IntentType
from gateway.core.classifier.rules import classify_intent

test_tasks = [
    ("Add retry logic to Stripe integration", IntentType.FEATURE_ADDITION),
    ("How does authentication work?", IntentType.ARCHITECTURAL_QUESTION),
    ("Fix the null pointer in payment flow", IntentType.BUG_FIX),
    ("Refactor UserService to use repository pattern", IntentType.REFACTOR),
]

print("Testing classify_intent...\n")

for task, expected in test_tasks:
    intent, conf, keys = classify_intent(task)
    status = "✅" if intent == expected else "❌"
    print(f"{status} Task: {task}")
    print(f"  Intent: {intent}, Confidence: {conf:.2f}, Keywords: {keys}")
    print(f"  Expected: {expected}\n")
