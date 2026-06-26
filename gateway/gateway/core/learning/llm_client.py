"""LLM client wrapper (placeholder)."""

import structlog
from typing import Optional

from gateway.config import settings

logger = structlog.get_logger(__name__)


class LLMClient:
    """LLM client for classifier fallback."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.model = settings.llm_model

    async def classify(self, task: str) -> dict:
        """Classify a task using LLM fallback."""
        logger.info("Using LLM fallback classification", task=task[:50])
        # Placeholder for actual LLM call
        return {
            "intent": "bug_fix",
            "confidence": 0.85,
            "domain": "general",
            "risk_level": "medium",
        }


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
