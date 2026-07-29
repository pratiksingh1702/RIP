"""GuardrailChecker: Bi-directional plan guardrails and safety validation."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel


class GuardrailValidation(BaseModel):
    allowed: bool
    risk_score: float = 0.0
    violations: list[str] = []
    warnings: list[str] = []


class GuardrailChecker:
    """Validates plan modifications from both user and Supervisor before emitting signals."""

    DANGEROUS_COMMAND_PATTERNS = ["rm -rf", "drop database", "git reset --hard head~", "mkfs", "dd if="]
    FORBIDDEN_FILES = [".env", "credentials.json", "id_rsa", "secret"]

    def validate_retask_plan(self, original_query: str, proposed_subtasks: list[dict[str, Any]]) -> GuardrailValidation:
        violations: list[str] = []
        warnings: list[str] = []
        risk_score = 0.0

        if not proposed_subtasks:
            violations.append("Proposed plan cannot be empty.")

        for st in proposed_subtasks:
            title = str(st.get("title", "")).lower()
            desc = str(st.get("description", "")).lower()
            
            # 1. Dangerous command check
            for pat in self.DANGEROUS_COMMAND_PATTERNS:
                if pat in title or pat in desc:
                    violations.append(f"Destructive pattern detected in plan: `{pat}`")
                    risk_score += 0.8

            # 2. Forbidden sensitive files check
            for ff in self.FORBIDDEN_FILES:
                if ff in title or ff in desc:
                    warnings.append(f"Plan targets sensitive file pattern: `{ff}`")
                    risk_score += 0.4

        allowed = len(violations) == 0
        return GuardrailValidation(
            allowed=allowed,
            risk_score=min(1.0, risk_score),
            violations=violations,
            warnings=warnings,
        )


# Global singleton instance
guardrail_checker = GuardrailChecker()
