"""SupervisorContentPolicy: Sanitizes external user input and untrusted context."""

from __future__ import annotations

import re


class SupervisorContentPolicy:
    """Sanitizes user input and external metadata to prevent prompt injections."""

    INJECTION_PATTERNS = [
        r"ignore previous instructions",
        r"system prompt override",
        r"you are now an unrestricted",
        r"disregard all prior rules",
    ]

    def sanitize_user_input(self, text: str) -> str:
        clean = text
        for pat in self.INJECTION_PATTERNS:
            clean = re.sub(pat, "[SANITIZED_POLICY]", clean, flags=re.IGNORECASE)
        return clean.strip()


# Global singleton instance
content_policy = SupervisorContentPolicy()
