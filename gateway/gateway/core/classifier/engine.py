"""Intent classification engine."""

import structlog

from gateway.config import settings
from gateway.core.learning.llm_client import get_llm_client

from .models import ClassificationResult, IntentType, RiskLevel
from .rules import assess_risk, classify_intent, detect_domain

logger = structlog.get_logger(__name__)


class ClassifierEngine:
    """Main intent classification engine."""
    
    def __init__(self):
        self.fallback_threshold = settings.llm_fallback_threshold
        self.llm_client = get_llm_client()
    
    def classify(self, task: str) -> ClassificationResult:
        """
        Classify a task description.
        
        Synchronous callers get deterministic rule classification. Async gateway
        paths should call classify_async() so low-confidence work can use the
        LLM fallback without nesting event loops.
        """
        return self._rule_result(task, strategy="rules")

    async def classify_async(self, task: str) -> ClassificationResult:
        """Classify a task with async-safe LLM fallback."""
        result = self._rule_result(task, strategy="rules")
        if result.confidence >= self.fallback_threshold or not settings.llm_fallback_enabled:
            return result

        logger.info("Confidence below threshold, using LLM fallback", task=task[:50])
        try:
            llm_result = await self.llm_client.classify(task)
            return ClassificationResult(
                intent=IntentType(llm_result.get("intent", result.intent)),
                confidence=float(llm_result.get("confidence", result.confidence)),
                domain=llm_result.get("domain") or result.domain,
                risk_level=RiskLevel(llm_result.get("risk_level", result.risk_level)),
                strategy="llm_fallback",
                domain_keywords_found=result.domain_keywords_found,
                raw_task=task,
            )
        except Exception as e:
            logger.warning("LLM fallback failed, using rule-based", error=str(e))
            return result

    def _rule_result(self, task: str, strategy: str) -> ClassificationResult:
        """Build a classification result from local rules."""
        # Step 1: Rule-based classification
        intent, confidence, intent_keywords = classify_intent(task)
        
        # Step 2: Domain detection
        domain, domain_keywords = detect_domain(task)
        
        # Step 3: Risk assessment
        risk_level = assess_risk(intent, domain, task)

        return ClassificationResult(
            intent=intent,
            confidence=confidence,
            domain=domain or "general",
            risk_level=risk_level,
            strategy=strategy,
            domain_keywords_found=domain_keywords,
            raw_task=task
        )


def classify(task: str) -> ClassificationResult:
    """Convenience function to classify a task."""
    engine = ClassifierEngine()
    return engine.classify(task)
