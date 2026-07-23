"""Three-layer privacy: source exclusion, regex scanning, LLM pass."""

from __future__ import annotations
import re

REDACTION_PATTERNS = [
    (r'sk-[A-Za-z0-9]{32,}', '[REDACTED: API Key]'),
    (r'gsk_[A-Za-z0-9]{40,}', '[REDACTED: API Key]'),
    (r'AKIA[A-Z0-9]{16}', '[REDACTED: AWS Key]'),
    (r'ghp_[A-Za-z0-9]{36}', '[REDACTED: GitHub Token]'),
    (r'Bearer\s+[A-Za-z0-9\-_\.]+', '[REDACTED: Token]'),
    (r'password\s*[:=]\s*\S+', '[REDACTED: Password]'),
    (r'-----BEGIN.*?PRIVATE KEY-----.*?-----END.*?PRIVATE KEY-----', '[REDACTED: Private Key]'),
]

DEFAULT_EXCLUDED_PATTERNS = {"slack": ["#security", "#credentials"], "github": [], "jira": ["HR-*"]}

class PrivacyEngine:
    def __init__(self, excluded_patterns: dict | None = None):
        self.excluded_patterns = excluded_patterns or DEFAULT_EXCLUDED_PATTERNS
    
    def should_exclude(self, source: str, channel_or_repo: str) -> bool:
        patterns = self.excluded_patterns.get(source, [])
        for pattern in patterns:
            if pattern.endswith("*") and channel_or_repo.startswith(pattern[:-1]): return True
            elif channel_or_repo == pattern: return True
        return False
    
    def redact_regex(self, text: str) -> tuple[str, int]:
        redactions = 0
        for pattern, replacement in REDACTION_PATTERNS:
            new_text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)
            if new_text != text: redactions += 1
            text = new_text
        return text, redactions
    
    async def redact_llm(self, text: str) -> str:
        try:
            from gateway.core.llm_pool.router import get_llm_router
            router = get_llm_router()
            config = await router.get_config()
            prompt = f"Scan for credentials/PII. Reply CLEAN or REDACT:<reason>.\n\nText:\n{text[:1000]}"
            response = await router.query_llm(prompt=prompt, config=config, max_tokens=30)
            if "REDACT" in response.upper(): return "[REDACTED: LLM-detected sensitive content]"
        except Exception: pass
        return text

_privacy = PrivacyEngine()
def get_privacy_engine() -> PrivacyEngine: return _privacy
