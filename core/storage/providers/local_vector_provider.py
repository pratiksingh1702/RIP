"""Local vector provider with lightweight lexical scoring."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from core.graph.models import SearchResult
from core.parser.base import ParsedEntity
from core.runtime.capabilities import Capability
from core.storage.interfaces.vector_store import VectorStore
from core.storage.providers.local_paths import vector_path

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class LocalVectorProvider(VectorStore):
    name = "LocalVectorProvider"
    capabilities = {Capability.VECTOR_SEARCH, Capability.PERSISTENT_STORAGE}

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.path = vector_path(self.repo_root)
        self.entities: dict[str, dict[str, Any]] = {}

    async def setup(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.entities = data.get("entities", {})

    async def upsert_entities(
        self, entities: list[ParsedEntity], project_id: str, project_name: str | None = None
    ) -> int:
        removed_files = {entity.file_path for entity in entities}
        if removed_files:
            self.entities = {
                key: value
                for key, value in self.entities.items()
                if (
                    value.get("project_id") != project_id
                    or value.get("file_path") not in removed_files
                )
            }
        for entity in entities:
            text = " ".join(
                item
                for item in [
                    entity.name,
                    entity.fqn,
                    entity.entity_type,
                    entity.file_path,
                    entity.docstring or "",
                    entity.raw_code[:2000],
                ]
                if item
            )
            key = f"{project_id}:{entity.fqn}"
            self.entities[key] = {
                "project_id": project_id,
                "project_name": project_name or project_id,
                "entity_id": entity.fqn,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "file_path": entity.file_path,
                "language": entity.language,
                "raw_code": entity.raw_code,
                "tokens": dict(_tokens(text)),
            }
        await self._save()
        return len(entities)

    async def search_similar(
        self,
        query: str,
        project_id: str,
        limit: int = 20,
        filters: dict[str, object] | None = None,
    ) -> list[SearchResult]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        filters = filters or {}
        scored: list[tuple[float, dict[str, Any]]] = []
        for entity in self.entities.values():
            if entity.get("project_id") != project_id:
                continue
            if filters.get("language") and entity.get("language") != filters["language"]:
                continue
            if filters.get("entity_type") and entity.get("entity_type") != filters["entity_type"]:
                continue
            score = _cosine(query_tokens, Counter(entity.get("tokens", {})))
            if score > 0:
                scored.append((score, entity))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            SearchResult(
                entity_id=item["entity_id"],
                entity_type=item["entity_type"],
                name=item["name"],
                file_path=item["file_path"],
                language=item["language"],
                score=score,
                raw_code=item.get("raw_code", ""),
                project_id=item.get("project_id"),
            )
            for score, item in scored[:limit]
        ]

    async def delete_project(self, project_id: str) -> int:
        before = len(self.entities)
        self.entities = {
            key: value
            for key, value in self.entities.items()
            if value.get("project_id") != project_id
        }
        await self._save()
        return before - len(self.entities)

    async def close(self) -> None:
        await self._save()

    async def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"entities": self.entities}, indent=2), encoding="utf-8")


def _tokens(text: str) -> Counter[str]:
    return Counter(token.lower() for token in TOKEN_RE.findall(text))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    overlap = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in overlap)
    if numerator <= 0:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)
