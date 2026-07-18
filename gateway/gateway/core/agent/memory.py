"""Execution Memory - persists learnings across agent runs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileMemory:
    path: str
    risk_level: str = "low"
    times_modified: int = 0
    last_error: str | None = None
    successful_patterns: list[str] = field(default_factory=list)


@dataclass
class ProjectMemory:
    project_id: str
    files: dict[str, FileMemory] = field(default_factory=dict)
    successful_tools: list[str] = field(default_factory=list)
    failed_patterns: list[str] = field(default_factory=list)
    last_run_at: str = ""

    def record_file_change(self, path: str, success: bool, error: str | None = None):
        if path not in self.files:
            self.files[path] = FileMemory(path=path)
        fm = self.files[path]
        fm.times_modified += 1
        if not success:
            fm.last_error = error
            fm.risk_level = "high"
        elif fm.times_modified > 3:
            fm.risk_level = "medium"

    def record_successful_tool(self, tool_name: str):
        if tool_name not in self.successful_tools:
            self.successful_tools.append(tool_name)

    def record_failed_pattern(self, pattern: str):
        if pattern not in self.failed_patterns:
            self.failed_patterns.append(pattern)

    def get_risky_files(self) -> list[FileMemory]:
        return [f for f in self.files.values() if f.risk_level == "high"]

    def get_context_for_llm(self) -> str:
        """Generate context summary for the LLM."""
        risky = self.get_risky_files()
        lines = []
        if risky:
            lines.append("Previously risky files (be extra careful):")
            for f in risky[:5]:
                lines.append(f"  - {f.path} (modified {f.times_modified}x, last error: {f.last_error})")
        if self.failed_patterns:
            lines.append("Previously failed approaches (avoid these):")
            for p in self.failed_patterns[-3:]:
                lines.append(f"  - {p}")
        if self.successful_tools:
            lines.append(f"Previously successful tools: {', '.join(self.successful_tools[-5:])}")
        return "\n".join(lines)


class ExecutionMemory:
    """Persists project-level learnings across agent runs."""

    def __init__(self, storage_path: str = ".repo-intel/agent_memory.json"):
        self.storage_path = Path(storage_path)
        self.projects: dict[str, ProjectMemory] = {}
        self._load()

    def _load(self):
        try:
            if self.storage_path.exists():
                data = json.loads(self.storage_path.read_text())
                for pid, pdata in data.get("projects", {}).items():
                    pm = ProjectMemory(project_id=pid)
                    for fpath, fdata in pdata.get("files", {}).items():
                        pm.files[fpath] = FileMemory(
                            path=fpath,
                            risk_level=fdata.get("risk_level", "low"),
                            times_modified=fdata.get("times_modified", 0),
                            last_error=fdata.get("last_error"),
                            successful_patterns=fdata.get("successful_patterns", []),
                        )
                    pm.successful_tools = pdata.get("successful_tools", [])
                    pm.failed_patterns = pdata.get("failed_patterns", [])
                    pm.last_run_at = pdata.get("last_run_at", "")
                    self.projects[pid] = pm
                logger.info("MEMORY: Loaded memory for %d projects", len(self.projects))
        except Exception as e:
            logger.warning("MEMORY: Failed to load memory: %s", e)

    def _save(self):
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"projects": {}}
            for pid, pm in self.projects.items():
                data["projects"][pid] = {
                    "files": {
                        fp: {
                            "risk_level": fm.risk_level,
                            "times_modified": fm.times_modified,
                            "last_error": fm.last_error,
                            "successful_patterns": fm.successful_patterns,
                        }
                        for fp, fm in pm.files.items()
                    },
                    "successful_tools": pm.successful_tools,
                    "failed_patterns": pm.failed_patterns,
                    "last_run_at": pm.last_run_at,
                }
            self.storage_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error("MEMORY: Failed to save memory: %s", e)

    def get_project(self, project_id: str) -> ProjectMemory:
        if project_id not in self.projects:
            self.projects[project_id] = ProjectMemory(project_id=project_id)
        return self.projects[project_id]

    def record_result(self, project_id: str, file_path: str, success: bool, error: str | None, tool_name: str):
        pm = self.get_project(project_id)
        pm.record_file_change(file_path, success, error)
        if success:
            pm.record_successful_tool(tool_name)
        else:
            pm.record_failed_pattern(f"{tool_name} on {file_path}: {error}")
        pm.last_run_at = datetime.now(UTC).isoformat()
        self._save()

    def get_context(self, project_id: str) -> str:
        pm = self.get_project(project_id)
        return pm.get_context_for_llm()


_memory = ExecutionMemory()


def get_execution_memory() -> ExecutionMemory:
    return _memory
