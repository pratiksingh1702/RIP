"""Rule-based classification logic."""

from .models import IntentType, RiskLevel
from .patterns import DOMAIN_PATTERNS, INTENT_KEYWORDS


def extract_keywords(text: str, keyword_list: list[str]) -> list[str]:
    """Extract keywords from text using case-insensitive matching."""
    found = []
    text_lower = text.lower()
    for keyword in keyword_list:
        if keyword.lower() in text_lower:
            found.append(keyword)
    return found


def classify_intent(task: str) -> tuple[IntentType, float, list[str]]:
    """
    Classify intent using rule-based keyword matching.
    
    Returns: (intent_type, confidence, matching_keywords)
    """
    intent_scores = {}
    
    for intent, keywords in INTENT_KEYWORDS.items():
        found = extract_keywords(task, keywords)
        # Score is number of unique matching keywords
        intent_scores[intent] = (len(set(found)), found)
    
    # Find the intent with highest score
    sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1][0], reverse=True)
    
    if sorted_intents:
        best_intent, (score, found_keywords) = sorted_intents[0]
        
        if score > 0:
            # Calculate confidence based on score and total unique keywords for that intent
            max_possible = len(set(INTENT_KEYWORDS[best_intent]))
            confidence = min(1.0, score / max(1, max_possible) * 1.5)  # Boost slightly
            return (IntentType(best_intent), confidence, found_keywords)
    
    # Default to investigation if no matches
    return (IntentType.INVESTIGATION, 0.3, [])


def detect_domain(task: str) -> tuple[str | None, list[str]]:
    """
    Detect domain using keyword matching.
    
    Returns: (domain, domain_keywords_found)
    """
    domain_scores = {}
    
    for domain, keywords in DOMAIN_PATTERNS.items():
        found = extract_keywords(task, keywords)
        domain_scores[domain] = len(set(found))
    
    sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
    
    if sorted_domains and sorted_domains[0][1] > 0:
        best_domain, score = sorted_domains[0]
        found_keywords = extract_keywords(task, DOMAIN_PATTERNS[best_domain])
        return (best_domain, found_keywords)
    
    return (None, [])


def assess_risk(intent: IntentType, domain: str | None, task: str) -> RiskLevel:
    """Assess risk level based on intent, domain, and task content."""
    # High risk keywords
    high_risk_domains = ["payment", "auth"]
    high_risk_keywords = ["database", "migration", "api", "public"]
    
    domain_lower = domain.lower() if domain else ""
    task_lower = task.lower()
    
    # Check for high risk indicators
    has_high_risk_domain = domain_lower in high_risk_domains
    has_high_risk_keywords = any(k in task_lower for k in high_risk_keywords)
    
    if has_high_risk_domain or has_high_risk_keywords:
        return RiskLevel.HIGH
    
    # Check for medium risk indicators
    if intent in [IntentType.FEATURE_ADDITION, IntentType.REFACTOR]:
        return RiskLevel.MEDIUM
    
    # Default to low risk
    return RiskLevel.LOW
