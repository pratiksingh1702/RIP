"""PlanAnalyzer: Evaluates planned DAG subtasks and AST diffs against repository knowledge."""

from __future__ import annotations

from typing import Any
from gateway.core.agent.impact_checker import impact_checker
from gateway.core.agent.task_state import FilePlan, StepStatus


class PlanAnalyzer:
    """Inspects step plans and generates file impact assessments."""

    def analyze_step_plans(
        self,
        steps: list[StepStatus],
        repo_root: str | None = None,
    ) -> dict[str, Any]:
        file_plans: list[FilePlan] = []
        max_risk = "low"
        total_dependents = 0

        for step in steps:
            for target_file in step.target_files:
                deps, high_fan, risk = impact_checker.analyze_file(target_file, repo_root)
                fp = FilePlan(
                    file_path=target_file,
                    rationale=step.description or step.title,
                    has_high_fan_in=high_fan,
                    dependent_count=deps,
                )
                file_plans.append(fp)
                total_dependents += deps
                if risk == "high" or (risk == "medium" and max_risk == "low"):
                    max_risk = risk

        return {
            "file_plans": [fp.model_dump() for fp in file_plans],
            "overall_risk": max_risk,
            "total_files": len(file_plans),
            "high_fan_in_count": sum(1 for fp in file_plans if fp.has_high_fan_in),
        }


# Global singleton instance
plan_analyzer = PlanAnalyzer()
