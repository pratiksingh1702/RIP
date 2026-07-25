"""Injection Scanner — detects prompt injection patterns in external content. Best-effort only."""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    (r'ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|messages?)', "Role override: 'ignore previous instructions'"),
    (r'you\s+are\s+(now\s+)?(an?\s+)?(unfiltered|uncensored|evil|malicious|DAN)', "Role switching: 'you are now...'"),
    (r'pretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(unfiltered|uncensored|different)', "Pretend directive"),
    (r'do\s+not\s+(follow|obey|listen\s+to)\s+(your\s+)?(instructions?|system\s+prompt)', "Instruction override"),
    (r'you\s+must\s+(respond|answer|reply)\s+(with|as|in\s+the\s+style\s+of)', "Forced response pattern"),
    (r'\[SYSTEM\]|\[INST\]|\[ASSISTANT\]|\[USER\]', "System prompt injection via brackets"),
    (r'<\|im_start\|>|<\|im_end\|>', "ChatML injection tokens"),
    (r'<script>|javascript:|onerror=|onload=', "XSS patterns in content"),
    (r'base64[,:]', "Potential obfuscated content"),
]

@dataclass
class ScanResult:
    clean: bool = True
    findings: list[dict] = field(default_factory=list)
    risk_level: str = "none"

class InjectionScanner:
    """Scans external content for prompt injection patterns. Best-effort — not a guarantee."""

    def scan(self, content: str, source: str = "unknown") -> ScanResult:
        """Scan content for injection patterns."""
        findings = []
        for pattern, description in INJECTION_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                findings.append({"pattern": pattern, "description": description, "matches": len(matches), "source": source})
        risk = "none"
        if len(findings) >= 3:
            risk = "high"
        elif len(findings) >= 1:
            risk = "low"
        if findings:
            logger.warning("Injection scanner: %d findings in %s content, risk=%s", len(findings), source, risk)
        return ScanResult(clean=len(findings) == 0, findings=findings, risk_level=risk)

    def scan_all(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        """Scan all items. Returns (clean_items, flagged_items)."""
        clean, flagged = [], []
        for item in items:
            source = item.get("source", "unknown")
            result = self.scan(item.get("content", ""), source)
            if result.clean:
                clean.append(item)
            else:
                flagged.append({**item, "scan_result": result})
                logger.info("Content flagged from %s: risk=%s, findings=%d", source, result.risk_level, len(result.findings))
        return clean, flagged

_scanner: InjectionScanner | None = None
def get_injection_scanner() -> InjectionScanner:
    global _scanner
    if _scanner is None:
        _scanner = InjectionScanner()
    return _scanner
