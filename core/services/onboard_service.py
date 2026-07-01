"""Onboarding domain service."""

from __future__ import annotations


class OnboardService:
    def __init__(self, graph_store) -> None:
        self.graph_store = graph_store

    async def markdown(self, project_id: str, storage_description: str, mode: str) -> str:
        data = await self.graph_store.architecture(project_id)
        return "\n".join(
            [
                "# Repository Onboarding",
                "",
                "## Runtime",
                "",
                f"- Mode: {mode}",
                f"- Storage: {storage_description}",
                "",
                "## Modules",
                "",
                *[f"- {name}" for name in data.get("services", [])[:100]],
                "",
                "## Dependency Graph",
                "",
                "```mermaid",
                str(data.get("mermaid", "graph TD")),
                "```",
            ]
        )
