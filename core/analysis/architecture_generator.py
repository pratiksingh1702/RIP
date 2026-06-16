"""Architecture generation engine."""

from __future__ import annotations

import re

from core.analysis.base import BaseAnalyser
from core.graph.queries.architecture import get_architecture_data


def _safe_id(name: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", name)
    return cleaned or "unknown"


class ArchitectureGenerator(BaseAnalyser):
    """Generates Mermaid diagrams and JSON service maps."""

    async def generate(self) -> dict[str, object]:
        """Generate architecture data and Mermaid diagram."""
        data = await get_architecture_data(self.graph_client)
        services = data["services"]
        dependencies = data["dependencies"]

        return {
            "services": services,
            "dependencies": dependencies,
            "mermaid": self.generate_mermaid(services, dependencies),
        }

    def generate_mermaid(
        self,
        class_data: list[dict[str, object]],
        module_data: list[dict[str, object]],
    ) -> str:
        lines = ["graph TD"]
        added_nodes: set[str] = set()
        added_edges: set[tuple[str, str, str]] = set()

        for item in class_data:
            name = str(item.get("class_name") or "")
            if name and name not in added_nodes:
                lines.append(f"    {_safe_id(name)}[{name}]")
                added_nodes.add(name)

        for item in class_data:
            name = str(item.get("class_name") or "")
            if not name:
                continue
            for parent in item.get("extends", []) or []:
                if not parent:
                    continue
                parent_name = str(parent)
                if parent_name not in added_nodes:
                    lines.append(f"    {_safe_id(parent_name)}[{parent_name}]")
                    added_nodes.add(parent_name)
                edge = (name, parent_name, "extends")
                if edge not in added_edges:
                    lines.append(
                        f"    {_safe_id(name)} -->|extends| {_safe_id(parent_name)}"
                    )
                    added_edges.add(edge)
            for iface in item.get("implements", []) or []:
                if not iface:
                    continue
                iface_name = str(iface)
                if iface_name not in added_nodes:
                    lines.append(f"    {_safe_id(iface_name)}[{iface_name}]")
                    added_nodes.add(iface_name)
                edge = (name, iface_name, "implements")
                if edge not in added_edges:
                    lines.append(
                        f"    {_safe_id(name)} -->|implements| {_safe_id(iface_name)}"
                    )
                    added_edges.add(edge)
            for called in item.get("calls_into", []) or []:
                if not called or called == name:
                    continue
                called_name = str(called)
                if called_name not in added_nodes:
                    lines.append(f"    {_safe_id(called_name)}[{called_name}]")
                    added_nodes.add(called_name)
                edge = (name, called_name, "calls")
                if edge not in added_edges:
                    lines.append(f"    {_safe_id(name)} -->|calls| {_safe_id(called_name)}")
                    added_edges.add(edge)

        for dep in module_data:
            source = str(dep.get("source") or "")
            target = str(dep.get("target") or "")
            if not source or not target or source == target:
                continue
            edge = (source, target, "depends")
            if edge not in added_edges:
                lines.append(f"    {_safe_id(source)} -->|depends| {_safe_id(target)}")
                added_edges.add(edge)

        if len(lines) == 1:
            lines.append("    note[No architecture data - run repo index first]")

        return "\n".join(lines)
