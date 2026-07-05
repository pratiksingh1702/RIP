"""Terminal execution block."""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext


class TerminalRunTestsBlock(Block):
    id = "terminal.run_tests"
    kind = BlockKind.VERIFICATION
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout": {"type": "number"},
        },
        "required": ["command"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "returncode": {"type": "number"},
        },
    }
    config_schema = {}
    requires_capabilities = []
    allowed_commands = {
        "pytest",
        "python -m pytest",
        "uv run pytest",
        "npm test",
        "npm run test",
        "flutter test",
        "dart test",
        "cargo test",
        "go test",
    }

    def _is_allowed_command(self, command: str) -> bool:
        normalized = " ".join(command.strip().split())
        return any(
            normalized == allowed or normalized.startswith(f"{allowed} ")
            for allowed in self.allowed_commands
        )

    def _is_allowed_cwd(self, cwd: str | None) -> bool:
        if not cwd:
            return True
        try:
            target = os.path.abspath(cwd)
            workspace = os.path.abspath(os.getcwd())
            return target == workspace or target.startswith(workspace + os.sep)
        except OSError:
            return False

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            command = str(inputs["command"]).strip()
            if not self._is_allowed_command(command):
                return BlockResult(ok=False, error=f"Command is not allow-listed: {command}")
            if not self._is_allowed_cwd(inputs.get("cwd")):
                return BlockResult(ok=False, error="cwd must stay inside the workspace")
            args = shlex.split(command, posix=os.name != "nt")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    args,
                    shell=False,
                    capture_output=True,
                    text=True,
                    cwd=inputs.get("cwd"),
                    timeout=inputs.get("timeout", 300),
                ),
            )
            return BlockResult(
                ok=result.returncode == 0,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                },
            )
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Run Tests",
            "description": "Run tests in a terminal",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }
