"""Intent classification engine."""

import asyncio
import structlog

from gateway.config import settings
from gateway.core.learning.llm_client import get_llm_client
from .models import ClassificationResult
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
        
        First tries rule-based classification. If confidence is below threshold,
        it uses LLM fallback.
        """
        # Step 1: Rule-based classification
        intent, confidence, intent_keywords = classify_intent(task)
        
        # Step 2: Domain detection
        domain, domain_keywords = detect_domain(task)
        
        # Step 3: Risk assessment
        risk_level = assess_risk(intent, domain, task)
        
        # Step 4: LLM fallback if needed
        if confidence < self.fallback_threshold:
            logger.info("Confidence below threshold, using LLM fallback", task=task[:50])
            try:
                loop = asyncio.get_event_loop()
                llm_result = loop.run_until_complete(self.llm_client.classify(task))
                intent = llm_result["intent"]
                confidence = llm_result["confidence"]
                domain = llm_result["domain"]
                risk_level = llm_result["risk_level"]
                strategy = "llm_fallback"
            except Exception as e:
                logger.warning("LLM fallback failed, using rule-based", error=str(e))
                strategy = "rules"
        else:
            strategy = "rules"
        
        # Step 5: Build result
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
