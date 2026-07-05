"""LLM client wrapper for classifier fallback."""

from __future__ import annotations

import json

import structlog

from gateway.config import settings
from gateway.core.classifier.rules import assess_risk, classify_intent, detect_domain

logger = structlog.get_logger(__name__)


class LLMClient:
    """Small structured-output LLM client for ambiguous classification."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        # Set GOOGLE_API_KEY env var if available in settings
        import os
        if settings.google_api_key:
            os.environ["GOOGLE_API_KEY"] = settings.google_api_key

    async def classify(self, task: str) -> dict:
        """Classify a task using an LLM, with a deterministic fallback."""
        logger.info("Using LLM fallback classification", task=task[:50])
        try:
            from litellm import acompletion

            response = await acompletion(
                model=self._model_name(),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify coding-agent tasks. Return only JSON with "
                            "intent, confidence, domain, and risk_level. "
                            "intent must be one of bug_fix, feature_addition, "
                            "refactor, architectural_question, investigation, documentation. "
                            "risk_level must be low, medium, or high."
                        ),
                    },
                    {"role": "user", "content": task},
                ],
                temperature=0,
                max_tokens=200,
            )
            content = response.choices[0].message.content or "{}"
            return self._validate(json.loads(self._strip_fences(content)), task)
        except Exception as exc:
            logger.warning("LLM classification unavailable", error=str(exc))
            return self._local_fallback(task)

    def _model_name(self) -> str:
        if self.provider == "ollama":
            return f"ollama/{self.model}"
        elif self.provider == "openrouter":
            return f"openrouter/{self.model}"
        elif self.provider == "anthropic":
            return f"anthropic/{self.model}"
        elif self.provider == "google":
            return f"gemini/{self.model}"
        elif self.provider == "groq":
            return f"groq/{self.model}"
        elif self.provider == "azure":
            return f"azure/{self.model}"
        elif self.provider and "/" not in self.model:
            return f"{self.provider}/{self.model}"
        return self.model

    def _strip_fences(self, content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
        return content.strip()

    def _validate(self, data: dict, task: str) -> dict:
        fallback = self._local_fallback(task)
        intent = data.get("intent") or fallback["intent"]
        risk = data.get("risk_level") or fallback["risk_level"]
        if intent not in {
            "bug_fix",
            "feature_addition",
            "refactor",
            "architectural_question",
            "investigation",
            "documentation",
        }:
            intent = fallback["intent"]
        if risk not in {"low", "medium", "high"}:
            risk = fallback["risk_level"]
        return {
            "intent": intent,
            "confidence": min(1.0, max(0.0, float(data.get("confidence", fallback["confidence"])))),
            "domain": data.get("domain") or fallback["domain"],
            "risk_level": risk,
        }

    def _local_fallback(self, task: str) -> dict:
        intent, confidence, _ = classify_intent(task)
        domain, _ = detect_domain(task)
        risk = assess_risk(intent, domain, task)
        return {
            "intent": intent.value,
            "confidence": max(confidence, 0.5),
            "domain": domain or "general",
            "risk_level": risk.value,
        }


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
