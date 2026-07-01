"""Local graph provider.

The provider intentionally keeps the public provider name as NetworkXProvider
because that is the planned local graph backend. It uses a small internal
adjacency representation so local mode works in the existing environment even
before adding a new dependency.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from core.graph.models import FlowHop, FlowTrace, GraphEdge, GraphNode, ImpactResult
from core.parser.base import ParsedFile
from core.runtime.capabilities import Capability
from core.storage.interfaces.graph_store import GraphStore
from core.storage.providers.local_paths import graph_path


class NetworkXProvider(GraphStore):
    name = "NetworkXProvider"
    capabilities = {
        Capability.GRAPH_TRAVERSAL,
        Capability.PERSISTENT_STORAGE,
        Capability.INCREMENTAL_INDEX,
    }

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.path = graph_path(self.repo_root)
        self.files: dict[str, dict[str, Any]] = {}
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []

    async def setup(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.files = data.get("files", {})
        self.nodes = data.get("nodes", {})
        self.edges = data.get("edges", [])

    async def batch_upsert_files(self, files: list[ParsedFile], project_id: str) -> dict[str, int]:
        removed_paths = {item.file_path for item in files}
        if removed_paths:
            self.nodes = {
                key: value
                for key, value in self.nodes.items()
                if (
                    value.get("file_path") not in removed_paths
                    or value.get("project_id") != project_id
                )
            }
            self.edges = [
                edge
                for edge in self.edges
                if (
                    edge.get("file_path") not in removed_paths
                    or edge.get("project_id") != project_id
                )
            ]

        entity_count = 0
        rel_count = 0
        for parsed in files:
            self.files[f"{project_id}:{parsed.file_path}"] = {
                "file_path": parsed.file_path,
                "language": parsed.language,
                "imports": parsed.imports,
                "sha256_hash": parsed.sha256_hash,
                "project_id": project_id,
            }
            for entity in parsed.entities:
                key = self._node_key(project_id, entity.fqn)
                self.nodes[key] = {
                    "id": key,
                    "label": entity.entity_type.title(),
                    "entity_type": entity.entity_type,
                    "name": entity.name,
                    "fqn": entity.fqn,
                    "file_path": entity.file_path,
                    "language": entity.language,
                    "line_start": entity.line_start,
                    "line_end": entity.line_end,
                    "raw_code": entity.raw_code,
                    "project_id": project_id,
                }
                entity_count += 1
            for rel in parsed.relationships:
                self.edges.append(
                    {
                        "source": self._node_key(project_id, rel.from_fqn),
                        "target": self._node_key(project_id, rel.to_fqn),
                        "source_fqn": rel.from_fqn,
                        "target_fqn": rel.to_fqn,
                        "relationship_type": rel.relationship_type,
                        "file_path": rel.file_path,
                        "line": rel.line,
                        "project_id": project_id,
                    }
                )
                rel_count += 1
            for imported in parsed.imports:
                self.edges.append(
                    {
                        "source": f"{project_id}:file:{parsed.file_path}",
                        "target": f"{project_id}:file:{imported}",
                        "source_fqn": parsed.file_path,
                        "target_fqn": imported,
                        "relationship_type": "IMPORTS",
                        "file_path": parsed.file_path,
                        "line": None,
                        "project_id": project_id,
                    }
                )
                rel_count += 1
        await self._save()
        return {"files": len(files), "entities": entity_count, "relationships": rel_count}

    async def trace(self, symbol: str, project_id: str, depth: int = 8) -> FlowTrace:
        start_keys = self._matching_node_keys(symbol, project_id)
        adjacency = defaultdict(list)
        for edge in self._project_edges(project_id):
            adjacency[edge["source"]].append(edge)

        hops: list[FlowHop] = []
        seen_edges: set[tuple[str, str, str]] = set()
        queue = deque((key, 0) for key in start_keys)
        seen_nodes = set(start_keys)
        while queue:
            key, distance = queue.popleft()
            if distance >= depth:
                continue
            for edge in adjacency.get(key, []):
                target = edge["target"]
                edge_key = (edge["source"], target, edge["relationship_type"])
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    hops.append(
                        FlowHop(
                            from_symbol=self._display_name(edge["source"]),
                            to_symbol=self._display_name(target),
                            relationship_type=edge["relationship_type"],
                            file_path=edge.get("file_path"),
                            line=edge.get("line"),
                        )
                    )
                if target not in seen_nodes:
                    seen_nodes.add(target)
                    queue.append((target, distance + 1))

        if not hops:
            hops = self._neighbor_hops(symbol, project_id)
        return FlowTrace(entry_point=symbol, hops=hops, mermaid=self._to_mermaid(hops))

    async def dependencies(self, target: str, project_id: str) -> list[GraphEdge]:
        matches = set(self._matching_node_keys(target, project_id))
        matches.add(f"{project_id}:file:{target}")
        rows: list[GraphEdge] = []
        for edge in self._project_edges(project_id):
            if edge["source"] in matches or edge.get("source_fqn") == target:
                rows.append(
                    GraphEdge(
                        source=edge.get("source_fqn") or edge["source"],
                        target=edge.get("target_fqn") or edge["target"],
                        relationship_type=edge["relationship_type"],
                        properties={"file_path": edge.get("file_path"), "line": edge.get("line")},
                    )
                )
        return rows

    async def architecture(self, project_id: str) -> dict[str, object]:
        modules: dict[str, set[str]] = defaultdict(set)
        for edge in self._project_edges(project_id):
            source_module = self._module_for(edge.get("source_fqn") or edge["source"])
            target_module = self._module_for(edge.get("target_fqn") or edge["target"])
            if source_module and target_module and source_module != target_module:
                modules[source_module].add(target_module)

        lines = ["graph TD"]
        dependencies = []
        for source, targets in sorted(modules.items()):
            for target in sorted(targets):
                lines.append(f'    "{source}" --> "{target}"')
                dependencies.append({"source": source, "target": target})
        if len(lines) == 1:
            lines.append('    "local-index"["Local index"]')
        return {
            "services": sorted(
                set(modules) | {item for targets in modules.values() for item in targets}
            ),
            "dependencies": dependencies,
            "mermaid": "\n".join(lines),
        }

    async def impact(self, symbol: str, project_id: str) -> ImpactResult:
        starts = set(self._matching_node_keys(symbol, project_id))
        reverse = defaultdict(list)
        for edge in self._project_edges(project_id):
            reverse[edge["target"]].append(edge)
        affected_nodes: dict[str, GraphNode] = {}
        affected_files: set[str] = set()
        queue = deque(starts)
        seen = set(starts)
        while queue:
            key = queue.popleft()
            node = self.nodes.get(key)
            if node:
                affected_nodes[key] = self._graph_node(node)
                if node.get("file_path"):
                    affected_files.add(node["file_path"])
            for edge in reverse.get(key, []):
                source = edge["source"]
                if source not in seen:
                    seen.add(source)
                    queue.append(source)
        count = len(affected_nodes)
        risk = "high" if count >= 15 else ("medium" if count >= 5 else "low")
        return ImpactResult(
            symbol=symbol,
            affected_files=sorted(affected_files),
            risk_level=risk,
            affected_nodes=list(affected_nodes.values()),
        )

    async def find_unused(self, project_id: str, entity_type: str = "all") -> list[GraphNode]:
        incoming = {edge["target"] for edge in self._project_edges(project_id)}
        unused: list[GraphNode] = []
        for key, node in self.nodes.items():
            if node.get("project_id") != project_id:
                continue
            if entity_type != "all" and node.get("entity_type") != entity_type.rstrip("s"):
                continue
            if key not in incoming and node.get("entity_type") not in {"module"}:
                unused.append(self._graph_node(node))
        return unused

    async def delete_project(self, project_id: str) -> int:
        before = len(self.nodes)
        self.files = {k: v for k, v in self.files.items() if v.get("project_id") != project_id}
        self.nodes = {k: v for k, v in self.nodes.items() if v.get("project_id") != project_id}
        self.edges = [edge for edge in self.edges if edge.get("project_id") != project_id]
        await self._save()
        return before - len(self.nodes)

    async def close(self) -> None:
        await self._save()

    async def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"files": self.files, "nodes": self.nodes, "edges": self.edges}, indent=2),
            encoding="utf-8",
        )

    def _project_edges(self, project_id: str) -> list[dict[str, Any]]:
        return [edge for edge in self.edges if edge.get("project_id") == project_id]

    def _matching_node_keys(self, symbol: str, project_id: str) -> list[str]:
        lowered = symbol.lower()
        matches = []
        for key, node in self.nodes.items():
            if node.get("project_id") != project_id:
                continue
            if (
                node.get("name") == symbol
                or node.get("fqn") == symbol
                or lowered in str(node.get("name", "")).lower()
                or lowered in str(node.get("fqn", "")).lower()
            ):
                matches.append(key)
        return matches

    def _neighbor_hops(self, symbol: str, project_id: str) -> list[FlowHop]:
        matches = set(self._matching_node_keys(symbol, project_id))
        hops = []
        for edge in self._project_edges(project_id):
            if edge["source"] in matches or edge["target"] in matches:
                hops.append(
                    FlowHop(
                        from_symbol=self._display_name(edge["source"]),
                        to_symbol=self._display_name(edge["target"]),
                        relationship_type=edge["relationship_type"],
                        file_path=edge.get("file_path"),
                        line=edge.get("line"),
                    )
                )
        return hops

    def _display_name(self, key: str) -> str:
        node = self.nodes.get(key)
        if node:
            return str(node.get("name") or node.get("fqn") or key)
        return key.split(":", 1)[-1]

    def _graph_node(self, node: dict[str, Any]) -> GraphNode:
        return GraphNode(
            id=node["id"],
            label=node.get("label") or node.get("entity_type", "Entity").title(),
            name=node.get("name") or "",
            fqn=node.get("fqn"),
            file_path=node.get("file_path"),
            language=node.get("language"),
            properties={
                "line_start": node.get("line_start"),
                "line_end": node.get("line_end"),
                "entity_type": node.get("entity_type"),
            },
        )

    @staticmethod
    def _node_key(project_id: str, fqn: str) -> str:
        return f"{project_id}:{fqn}"

    @staticmethod
    def _module_for(value: str) -> str:
        value = value.replace("\\", "/")
        if "/" in value:
            parts = [part for part in value.split("/") if part]
            return parts[0] if parts else value
        return value.split(".")[0] if "." in value else value

    @staticmethod
    def _to_mermaid(hops: list[FlowHop]) -> str:
        lines = ["graph TD"]
        seen = set()
        for hop in hops[:50]:
            edge = (hop.from_symbol, hop.to_symbol, hop.relationship_type)
            if edge in seen:
                continue
            seen.add(edge)
            lines.append(f'    "{hop.from_symbol}" -->|{hop.relationship_type}| "{hop.to_symbol}"')
        return "\n".join(lines)
