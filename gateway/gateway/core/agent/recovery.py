"""Recovery Engine - self-healing for failed agent steps."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from gateway.core.llm_pool.router import LLMConfig, get_llm_router

logger = logging.getLogger(__name__)

RECOVERY_SYSTEM_PROMPT = """You are a software engineering recovery specialist. A previous attempt failed.

Given:
1. The original task
2. The tool that failed
3. The error message
4. Recent context

Provide a RECOVERY PLAN that either:
- Fixes the issue with a different approach
- Rolls back and tries an alternative
- Acknowledges the error and explains why it's unrecoverable

Output ONLY valid JSON:
{
    "recoverable": true,
    "recovery_action": "description of what to do differently",
    "alternative_approach": "different tool or strategy to try",
    "should_rollback": false,
    "explanation": "why this approach should work"
}
"""


@dataclass
class RecoveryPlan:
    recoverable: bool
    recovery_action: str = ""
    alternative_approach: str = ""
    should_rollback: bool = False
    explanation: str = ""


class RecoveryEngine:
    """Handles self-correction when agent steps fail."""

    MAX_RETRIES = 3

    def __init__(self):
        self.retry_counts: dict[str, int] = {}
        self.failed_tools: dict[str, list[dict]] = {}

    async def attempt_recovery(
        self,
        step_id: str,
        tool_name: str,
        error: str,
        original_query: str,
        recent_context: list[dict],
        llm_config: LLMConfig,
    ) -> RecoveryPlan | None:
        """Try to recover from a failed tool execution."""
        retries = self.retry_counts.get(step_id, 0)

        if retries >= self.MAX_RETRIES:
            logger.warning("RECOVERY: Max retries (%d) reached for step %s", self.MAX_RETRIES, step_id)
            return None

        self.retry_counts[step_id] = retries + 1

        # Record failure for learning
        if step_id not in self.failed_tools:
            self.failed_tools[step_id] = []
        self.failed_tools[step_id].append({"tool": tool_name, "error": error, "attempt": retries + 1})

        try:
            router = get_llm_router()
            context_str = json.dumps(recent_context[-5:] if len(recent_context) > 5 else recent_context, indent=2)

            prompt = f"""Original task: {original_query}

Failed tool: {tool_name}
Error: {error}
Attempt: {retries + 1}/{self.MAX_RETRIES}

Recent context:
{context_str}

Create a recovery plan."""

            response = await router.query_llm(
                prompt=prompt,
                config=llm_config,
                system_prompt=RECOVERY_SYSTEM_PROMPT,
                max_tokens=1000,
            )

            plan_data = self._parse_recovery(response)
            logger.info("RECOVERY: Plan for step %s - recoverable=%s action=%s", step_id, plan_data.get("recoverable"), plan_data.get("recovery_action", "")[:80])

            return RecoveryPlan(
                recoverable=bool(plan_data.get("recoverable", False)),
                recovery_action=str(plan_data.get("recovery_action", "")),
                alternative_approach=str(plan_data.get("alternative_approach", "")),
                should_rollback=bool(plan_data.get("should_rollback", False)),
                explanation=str(plan_data.get("explanation", "")),
            )

        except Exception as e:
            logger.error("RECOVERY: Recovery planning failed: %s", e)
            return None

    def _parse_recovery(self, response: str) -> dict:
        import re
        json_match = re.search(r'\{[^{}]*"recoverable"[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        return {"recoverable": False, "explanation": "Could not parse recovery plan"}

    def reset(self):
        """Reset retry counts for a new execution."""
        self.retry_counts.clear()
        self.failed_tools.clear()


_recovery = RecoveryEngine()


def get_recovery_engine() -> RecoveryEngine:
    return _recovery
