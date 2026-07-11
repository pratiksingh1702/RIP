"""Apply unified diff patches safely with backup creation."""

from __future__ import annotations

import os
import re
import shutil
from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext


class FSApplyPatchBlock(Block):
    id = "fs.apply_patch"
    kind = BlockKind.DEPLOYMENT
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to patch"},
            "diff": {"type": "string", "description": "Unified diff to apply"},
            "create_backup": {"type": "boolean", "default": True},
        },
        "required": ["path", "diff"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "backup": {"type": "string"},
            "lines_before": {"type": "integer"},
            "lines_after": {"type": "integer"},
            "success": {"type": "boolean"},
        },
    }
    config_schema = {"type": "object", "properties": {"base_path": {"type": "string"}}}
    requires_capabilities = []

    def _resolve_path(self, path: str, config: dict) -> str:
        base = config.get("base_path") or os.getcwd()
        if base in (".", ""):
            base = os.getcwd()
        full = os.path.normpath(os.path.join(base, path))
        if not full.startswith(os.path.normpath(base)):
            raise ValueError(f"Path traversal denied: {path}")
        return full

    def _apply_patch(self, original: str, diff: str) -> str | None:
        orig_lines = original.splitlines(keepends=True)
        hunks = list(re.finditer(r'@@ -(\d+),?\d* \+(\d+),?\d* @@.*?\n(.*?)(?=\n@@|\Z)', diff, re.DOTALL))
        if not hunks:
            return None
        result = list(orig_lines)
        offset = 0
        for hunk in hunks:
            orig_start = int(hunk.group(1)) - 1
            body = hunk.group(2)
            new_lines = []
            src_idx = orig_start
            for line in body.split('\n'):
                if not line:
                    continue
                if line.startswith(' '):
                    if src_idx < len(orig_lines):
                        new_lines.append(orig_lines[src_idx])
                    src_idx += 1
                elif line.startswith('-'):
                    src_idx += 1
                elif line.startswith('+'):
                    new_lines.append(line[1:] + '\n')
            result = result[:orig_start] + new_lines + result[orig_start + src_idx - orig_start:]
        return ''.join(result)

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            path = str(inputs["path"])
            diff = str(inputs["diff"])
            create_backup = bool(inputs.get("create_backup", True))
            full_path = self._resolve_path(path, config)

            if not os.path.exists(full_path):
                return BlockResult(ok=False, error=f"File not found: {path}")

            original = open(full_path, "r", encoding="utf-8").read()
            lines_before = original.count('\n')

            if create_backup:
                backup_path = full_path + ".orig"
                if not os.path.exists(backup_path):
                    shutil.copy2(full_path, backup_path)
            else:
                backup_path = None

            patched = self._apply_patch(original, diff)
            if patched is None:
                return BlockResult(ok=False, error="Patch could not be applied - no matching hunks found")

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(patched)

            lines_after = patched.count('\n')
            return BlockResult(ok=True, output={
                "path": full_path, "backup": backup_path,
                "lines_before": lines_before, "lines_after": lines_after,
                "success": True,
            })
        except ValueError as e:
            return BlockResult(ok=False, error=str(e))
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id, "kind": self.kind.value,
            "name": "Apply Patch", "description": "Apply a unified diff to a file with backup",
            "category": "Filesystem", "display_icon": "📝", "display_color": "#6366F1",
            "input_schema": self.input_schema, "output_schema": self.output_schema,
        }
