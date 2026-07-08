"""Filesystem blocks for reading and writing local files."""

from __future__ import annotations

import os
import glob
import json
from pathlib import Path
from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext


def _resolve_base_path(config: dict[str, Any]) -> str:
    base_path = config.get("base_path") or os.getcwd()
    if base_path in (".", ""):
        base_path = os.getcwd()
    return base_path


class FSReadFileBlock(Block):
    id = "fs.read_file"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
            "encoding": {"type": "string", "default": "utf-8"},
            "max_lines": {"type": "integer", "default": 1000},
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "lines": {"type": "integer"},
            "size_bytes": {"type": "integer"},
            "exists": {"type": "boolean"},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "base_path": {"type": "string", "description": "Restrict reads to this directory"},
            "allowed_extensions": {"type": "array", "items": {"type": "string"}},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            path = str(inputs["path"])
            base_path = _resolve_base_path(config)

            # Security: resolve and check path is within base
            full_path = os.path.normpath(os.path.join(base_path, path))
            if not full_path.startswith(os.path.normpath(base_path)):
                return BlockResult(ok=False, error=f"Path traversal denied: {path}")

            allowed = config.get("allowed_extensions")
            if allowed:
                ext = os.path.splitext(full_path)[1]
                if ext not in allowed:
                    return BlockResult(ok=False, error=f"Extension not allowed: {ext}")

            if not os.path.exists(full_path):
                return BlockResult(ok=True, output={"content": "", "lines": 0, "size_bytes": 0, "exists": False})

            size = os.path.getsize(full_path)
            max_lines = int(inputs.get("max_lines", 1000))
            encoding = str(inputs.get("encoding", "utf-8"))

            with open(full_path, "r", encoding=encoding) as f:
                lines_list = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines_list.append(f"... (truncated, {max_lines} line limit)")
                        break
                    lines_list.append(line.rstrip("\n"))
                content = "\n".join(lines_list)

            return BlockResult(ok=True, output={
                "content": content,
                "lines": len(lines_list),
                "size_bytes": size,
                "exists": True,
            })
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Read File", "description": "Read contents of a file", "category": "Filesystem", "display_icon": "📄", "display_color": "#6366F1", "input_schema": self.input_schema, "output_schema": self.output_schema}


class FSWriteFileBlock(Block):
    id = "fs.write_file"
    kind = BlockKind.DEPLOYMENT
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
            "encoding": {"type": "string", "default": "utf-8"},
            "create_dirs": {"type": "boolean", "default": True},
        },
        "required": ["path", "content"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "created": {"type": "boolean"},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "base_path": {"type": "string"},
            "allowed_extensions": {"type": "array"},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            path = str(inputs["path"])
            base_path = _resolve_base_path(config)
            full_path = os.path.normpath(os.path.join(base_path, path))
            if not full_path.startswith(os.path.normpath(base_path)):
                return BlockResult(ok=False, error=f"Path traversal denied: {path}")

            allowed = config.get("allowed_extensions")
            if allowed:
                ext = os.path.splitext(full_path)[1]
                if ext not in allowed:
                    return BlockResult(ok=False, error=f"Extension not allowed: {ext}")

            content = str(inputs["content"])
            encoding = str(inputs.get("encoding", "utf-8"))
            create_dirs = bool(inputs.get("create_dirs", True))
            existed = os.path.exists(full_path)

            if create_dirs:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w", encoding=encoding) as f:
                f.write(content)

            return BlockResult(ok=True, output={
                "path": full_path,
                "size_bytes": os.path.getsize(full_path),
                "created": not existed,
            })
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Write File", "description": "Write content to a file", "category": "Filesystem", "display_icon": "✏️", "display_color": "#6366F1", "input_schema": self.input_schema, "output_schema": self.output_schema}


class FSListDirectoryBlock(Block):
    id = "fs.list_directory"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to list"},
            "pattern": {"type": "string", "default": "*", "description": "Glob pattern"},
            "recursive": {"type": "boolean", "default": False},
            "max_results": {"type": "integer", "default": 100},
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "files": {"type": "array"},
            "count": {"type": "integer"},
            "directory": {"type": "string"},
        },
    }
    config_schema = {"type": "object", "properties": {"base_path": {"type": "string"}}}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            path = str(inputs["path"])
            base_path = _resolve_base_path(config)
            full_path = os.path.normpath(os.path.join(base_path, path))
            if not full_path.startswith(os.path.normpath(base_path)):
                return BlockResult(ok=False, error=f"Path traversal denied: {path}")
            if not os.path.isdir(full_path):
                return BlockResult(ok=False, error=f"Not a directory: {path}")

            pattern = str(inputs.get("pattern", "*"))
            recursive = bool(inputs.get("recursive", False))
            max_results = int(inputs.get("max_results", 100))

            search_pattern = os.path.join(full_path, "**", pattern) if recursive else os.path.join(full_path, pattern)
            results = []
            for i, match in enumerate(glob.iglob(search_pattern, recursive=recursive)):
                if i >= max_results:
                    break
                rel = os.path.relpath(match, full_path)
                is_dir = os.path.isdir(match)
                size = os.path.getsize(match) if not is_dir else 0
                results.append({"name": rel, "is_directory": is_dir, "size_bytes": size})

            return BlockResult(ok=True, output={"files": results, "count": len(results), "directory": full_path})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "List Directory", "description": "List files in a directory", "category": "Filesystem", "display_icon": "📁", "display_color": "#6366F1", "input_schema": self.input_schema, "output_schema": self.output_schema}


class FSSearchFilesBlock(Block):
    id = "fs.search_files"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "pattern": {"type": "string", "description": "Glob pattern like **/*.py"},
            "contains": {"type": "string", "description": "Text the file must contain"},
            "max_results": {"type": "integer", "default": 50},
        },
        "required": ["path", "pattern"],
    }
    output_schema = {"type": "object", "properties": {"matches": {"type": "array"}, "count": {"type": "integer"}}}
    config_schema = {"type": "object", "properties": {"base_path": {"type": "string"}}}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            path = str(inputs["path"])
            base_path = _resolve_base_path(config)
            full_path = os.path.normpath(os.path.join(base_path, path))
            if not full_path.startswith(os.path.normpath(base_path)):
                return BlockResult(ok=False, error=f"Path traversal denied: {path}")

            pattern = str(inputs["pattern"])
            contains = inputs.get("contains")
            max_results = int(inputs.get("max_results", 50))

            matches = []
            for i, match in enumerate(glob.iglob(os.path.join(full_path, pattern), recursive=True)):
                if i >= max_results:
                    break
                rel = os.path.relpath(match, full_path)
                if contains and os.path.isfile(match):
                    try:
                        with open(match, "r", encoding="utf-8", errors="ignore") as f:
                            if contains.lower() not in f.read().lower():
                                continue
                    except Exception:
                        continue
                matches.append({"path": rel, "size_bytes": os.path.getsize(match) if os.path.isfile(match) else 0})

            return BlockResult(ok=True, output={"matches": matches, "count": len(matches)})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Search Files", "description": "Find files by pattern", "category": "Filesystem", "display_icon": "🔍", "display_color": "#6366F1", "input_schema": self.input_schema, "output_schema": self.output_schema}