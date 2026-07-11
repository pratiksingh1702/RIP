"""Gateway-controlled Agent Runtime. The LLM reasons, the Gateway executes."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from gateway.core.agent.tools import ToolRegistry, ToolResult
from gateway.core.agent.llm_interface import LLMInterface, LLMResponse, ResponseType
from gateway.core.events import get_event_bus
from gateway.core.llm_pool.router import LLMConfig
from gateway.core.sources.rip_client import RIPSource
from gateway.storage.database import async_session_factory

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """You are an expert software engineer working inside Context Gateway.
You have access to tools for reading, searching, editing, and verifying code.

CRITICAL RULES:
1. Use RIP context provided below as GROUND TRUTH. Never guess architecture.
2. Make ONE tool call at a time. You will receive the result before continuing.
3. Always read a file before editing it.
4. Always trace dependencies before modifying shared functions.
5. Always run tests/verification after making changes.
6. If a tool fails, analyze the error and try a different approach.
7. When all changes are complete and verified, call the 'finish' tool with a summary.
8. Be thorough but efficient. Don't read unnecessary files.

AVAILABLE TOOLS:
{tool_descriptions}

RESPONSE FORMAT:
To use a tool, respond with ONLY this JSON on a single line:
{{"tool": "tool_name", "params": {{"param1": "value1", ...}}}}

To reason without calling a tool:
{{"thought": "Your reasoning here..."}}

To finish:
{{"tool": "finish", "params": {{"summary": "Complete summary of all changes made"}}}}
"""


@dataclass
class AgentStep:
    turn: int
    tool_name: str | None
    tool_params: dict | None
    tool_result: dict | None
    llm_response: str
    tokens_used: int
    timestamp: str


@dataclass
class AgentResult:
    query: str
    steps: list[dict]
    changes_made: list[dict]
    verification: dict | None
    summary: str
    tokens_total: int
    duration_seconds: float
    status: str
    error: str | None = None


class AgentRuntime:
    MAX_TURNS = 50

    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.llm_interface = LLMInterface()
        self.event_bus = get_event_bus()
        self._register_default_tools()

    def _register_default_tools(self):
        from gateway.core.agent.tools import ToolDefinition

        self.tool_registry.register(ToolDefinition(
            name="read_file",
            description="Read the contents of a file at the given path. Returns the file content, line count, and size.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to project root"}
                },
                "required": ["path"]
            },
            handler=self._tool_read_file,
        ))

        self.tool_registry.register(ToolDefinition(
            name="search_codebase",
            description="Search the codebase for relevant files, functions, and classes using semantic search.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"}
                },
                "required": ["query"]
            },
            handler=self._tool_search,
        ))

        self.tool_registry.register(ToolDefinition(
            name="trace_dependencies",
            description="Find all callers (who calls this) and callees (what this calls) for a function or class.",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Function or class name to trace"}
                },
                "required": ["symbol"]
            },
            handler=self._tool_trace,
        ))

        self.tool_registry.register(ToolDefinition(
            name="write_file",
            description="Write content to a file. Creates parent directories if needed. Returns the file path and size.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write to the file"}
                },
                "required": ["path", "content"]
            },
            handler=self._tool_write_file,
            requires_approval=True,
            risk_level="medium",
        ))

        self.tool_registry.register(ToolDefinition(
            name="apply_patch",
            description="Apply a unified diff patch to a file. Creates a .orig backup before applying. Returns what changed.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File to patch"},
                    "diff": {"type": "string", "description": "Unified diff format patch to apply"}
                },
                "required": ["path", "diff"]
            },
            handler=self._tool_apply_patch,
            requires_approval=True,
            risk_level="medium",
        ))

        self.tool_registry.register(ToolDefinition(
            name="run_command",
            description="Run a shell command. Use for running tests, linters, build commands. Returns stdout, stderr, and exit code.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                "required": ["command"]
            },
            handler=self._tool_run_command,
            risk_level="low",
        ))

        self.tool_registry.register(ToolDefinition(
            name="list_directory",
            description="List files in a directory. Returns file names, sizes, and whether they are directories.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"},
                    "pattern": {"type": "string", "default": "*", "description": "Glob pattern like *.py"}
                },
                "required": ["path"]
            },
            handler=self._tool_list_dir,
        ))

        self.tool_registry.register(ToolDefinition(
            name="finish",
            description="Call this when ALL changes are complete and verified. Provide a comprehensive summary.",
            parameters={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Complete summary of all changes made, files modified, and verification results"}
                },
                "required": ["summary"]
            },
            handler=self._tool_finish,
        ))

    async def _tool_read_file(self, params: dict, ctx: dict) -> ToolResult:
        import os
        path = str(params["path"])
        base = ctx.get("project_root", os.getcwd())
        full = os.path.normpath(os.path.join(base, path))
        if not full.startswith(os.path.normpath(base)):
            return ToolResult(ok=False, error=f"Path traversal denied: {path}")
        if not os.path.exists(full):
            return ToolResult(ok=False, error=f"File not found: {path}")
        try:
            with open(full, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return ToolResult(ok=True, output={
                "content": content,
                "lines": content.count("\n") + 1,
                "size_bytes": os.path.getsize(full),
            })
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_search(self, params: dict, ctx: dict) -> ToolResult:
        try:
            source = RIPSource()
            result = await source.query("search", {"query": params["query"], "limit": 10, "project_id": ctx.get("project_id")})
            return ToolResult(ok=result.success, output={"content": result.content, "metadata": result.metadata})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_trace(self, params: dict, ctx: dict) -> ToolResult:
        try:
            source = RIPSource()
            result = await source.query("trace", {"query": params["symbol"], "project_id": ctx.get("project_id")})
            return ToolResult(ok=result.success, output={"content": result.content, "metadata": result.metadata})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_write_file(self, params: dict, ctx: dict) -> ToolResult:
        import os
        path = str(params["path"])
        content = str(params["content"])
        base = ctx.get("project_root", os.getcwd())
        full = os.path.normpath(os.path.join(base, path))
        if not full.startswith(os.path.normpath(base)):
            return ToolResult(ok=False, error=f"Path traversal denied: {path}")
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            existed = os.path.exists(full)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(ok=True, output={
                "path": full, "size_bytes": os.path.getsize(full), "created": not existed
            })
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_apply_patch(self, params: dict, ctx: dict) -> ToolResult:
        import os, shutil
        path = str(params["path"])
        diff = str(params["diff"])
        base = ctx.get("project_root", os.getcwd())
        full = os.path.normpath(os.path.join(base, path))
        if not full.startswith(os.path.normpath(base)):
            return ToolResult(ok=False, error=f"Path traversal denied: {path}")
        if not os.path.exists(full):
            return ToolResult(ok=False, error=f"File not found: {path}")
        try:
            backup = full + ".orig"
            if not os.path.exists(backup):
                shutil.copy2(full, backup)
            original = open(full, "r", encoding="utf-8").read()
            patched = self._apply_unified_diff(original, diff)
            if patched is None:
                return ToolResult(ok=False, error="Failed to apply diff - patch did not match")
            with open(full, "w", encoding="utf-8") as f:
                f.write(patched)
            orig_lines = original.count("\n")
            new_lines = patched.count("\n")
            return ToolResult(ok=True, output={
                "path": full, "backup": backup,
                "lines_before": orig_lines, "lines_after": new_lines,
                "lines_changed": new_lines - orig_lines,
            })
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    def _apply_unified_diff(self, original: str, diff: str) -> str | None:
        """Simple unified diff parser. Handles standard @@ -a,b +c,d @@ hunks."""
        orig_lines = original.splitlines(keepends=True)
        result_lines = list(orig_lines)
        hunks = re.findall(r'@@ -(\d+),?\d* \+(\d+),?\d* @@(.*?)(?=@@|\Z)', diff, re.DOTALL)
        offset = 0
        for hunk in hunks:
            orig_start = int(hunk[0]) - 1
            hunk_lines = hunk[2].strip().split('\n')
            i = orig_start
            new_hunk = []
            for line in hunk_lines:
                if line.startswith(' '):
                    if i < len(orig_lines):
                        new_hunk.append(orig_lines[i])
                    i += 1
                elif line.startswith('-'):
                    i += 1
                elif line.startswith('+'):
                    new_hunk.append(line[1:] + ('\n' if not line[1:].endswith('\n') else ''))
            result_lines[orig_start:orig_start + len([l for l in hunk_lines if not l.startswith('+')])] = new_hunk
        return ''.join(result_lines)

    async def _tool_run_command(self, params: dict, ctx: dict) -> ToolResult:
        import subprocess
        try:
            result = subprocess.run(
                params["command"], shell=True, capture_output=True, text=True,
                timeout=300, cwd=ctx.get("project_root")
            )
            return ToolResult(ok=result.returncode == 0, output={
                "stdout": result.stdout[-5000:], "stderr": result.stderr[-2000:],
                "exit_code": result.returncode
            })
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, error="Command timed out after 300s")
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_list_dir(self, params: dict, ctx: dict) -> ToolResult:
        import os, glob as globmod
        path = str(params["path"])
        pattern = params.get("pattern", "*")
        base = ctx.get("project_root", os.getcwd())
        full = os.path.normpath(os.path.join(base, path))
        if not full.startswith(os.path.normpath(base)):
            return ToolResult(ok=False, error=f"Path traversal denied: {path}")
        if not os.path.isdir(full):
            return ToolResult(ok=False, error=f"Not a directory: {path}")
        try:
            files = []
            for match in globmod.iglob(os.path.join(full, pattern)):
                rel = os.path.relpath(match, full)
                is_dir = os.path.isdir(match)
                files.append({"name": rel, "is_directory": is_dir, "size_bytes": os.path.getsize(match) if not is_dir else 0})
            return ToolResult(ok=True, output={"files": files[:100], "count": len(files)})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_finish(self, params: dict, ctx: dict) -> ToolResult:
        return ToolResult(ok=True, output={"summary": params["summary"], "finished": True})

    async def execute(self, query: str, llm_config: LLMConfig, project_id: str, user_id: str, project_root: str = None) -> AgentResult:
        start_time = time.monotonic()
        ctx = {"project_id": project_id, "user_id": user_id, "project_root": project_root or str(Path.cwd())}
        
        logger.info("AGENT: Starting execution - query=%s project=%s", query[:100], project_id)
        await self.event_bus.publish("agent.started", workflow_run_id=str(uuid4()), payload={"query": query, "project_id": project_id})

        # Phase 1: Gather RIP context
        rip_context = await self._gather_rip_context(query, project_id)
        logger.info("AGENT: RIP context gathered - files=%d", len(rip_context.get("files", [])))

        # Phase 2: Build conversation
        tools_desc = self.tool_registry.get_for_llm()
        system_prompt = AGENT_SYSTEM_PROMPT.format(tool_descriptions=json.dumps(tools_desc, indent=2))
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {query}\n\nRIP Context (ground truth):\n{json.dumps(rip_context, indent=2)}\n\nStart by reading the most relevant files."}
        ]

        # Phase 3: Execute loop
        steps = []
        tokens_total = 0
        final_summary = ""
        changes_made = []
        status = "completed"

        try:
            for turn in range(self.MAX_TURNS):
                logger.info("AGENT: Turn %d/%d", turn + 1, self.MAX_TURNS)
                await self.event_bus.publish("agent.turn", payload={"turn": turn + 1, "status": "thinking"})

                response = await self.llm_interface.call_with_tools(messages, tools_desc, llm_config)
                tokens_total += response.tokens_used

                if response.type == ResponseType.TEXT:
                    steps.append(AgentStep(turn=turn+1, tool_name=None, tool_params=None, tool_result=None, llm_response=response.text, tokens_used=response.tokens_used, timestamp=datetime.now(UTC).isoformat()))
                    messages.append({"role": "assistant", "content": response.raw})
                    continue

                if response.type == ResponseType.TOOL_CALL:
                    tool_name = response.tool_name
                    tool_params = response.tool_params or {}
                    
                    await self.event_bus.publish("agent.turn", payload={"turn": turn+1, "tool": tool_name, "status": "executing"})
                    
                    tool = self.tool_registry.get(tool_name)
                    if not tool:
                        result = ToolResult(ok=False, error=f"Unknown tool: {tool_name}")
                    else:
                        result = await tool.handler(tool_params, ctx)
                    
                    steps.append(AgentStep(turn=turn+1, tool_name=tool_name, tool_params=tool_params, tool_result={"ok": result.ok, "output": result.output, "error": result.error}, llm_response=response.raw, tokens_used=response.tokens_used, timestamp=datetime.now(UTC).isoformat()))
                    
                    messages.append({"role": "assistant", "content": response.raw})
                    result_text = json.dumps({"tool": tool_name, "result": {"ok": result.ok, "output": result.output, "error": result.error}})
                    messages.append({"role": "user", "content": f"Tool result: {result_text}"})

                    if tool_name in ("write_file", "apply_patch"):
                        changes_made.append({"tool": tool_name, "params": tool_params, "result": result.output})
                    
                    if tool_name == "finish":
                        final_summary = tool_params.get("summary", "Task completed.")
                        status = "completed"
                        break
                    
                    continue

                if response.type == ResponseType.FINISH:
                    final_summary = response.finish_summary or "Task completed."
                    status = "completed"
                    break

            else:
                status = "max_turns"
                final_summary = f"Reached maximum {self.MAX_TURNS} turns without finishing."

        except Exception as e:
            logger.error("AGENT: Execution failed - %s", e)
            status = "failed"
            final_summary = f"Agent execution failed: {e}"

        # Phase 4: Verification
        verification = None
        if changes_made:
            verification = await self._run_verification(changes_made, ctx)

        duration = time.monotonic() - start_time
        logger.info("AGENT: Completed - status=%s turns=%d tokens=%d duration=%.1fs", status, len(steps), tokens_total, duration)
        
        await self.event_bus.publish("agent.completed", payload={"status": status, "turns": len(steps), "tokens": tokens_total, "changes": len(changes_made)})

        return AgentResult(
            query=query,
            steps=[{"turn": s.turn, "tool": s.tool_name, "params": s.tool_params, "result": s.tool_result, "tokens": s.tokens_used, "timestamp": s.timestamp} for s in steps],
            changes_made=changes_made,
            verification=verification,
            summary=final_summary,
            tokens_total=tokens_total,
            duration_seconds=duration,
            status=status,
        )

    async def _gather_rip_context(self, query: str, project_id: str) -> dict:
        try:
            source = RIPSource()
            results = await asyncio.gather(
                source.query("explain", {"query": query, "limit": 5, "project_id": project_id}),
                source.query("search", {"query": query, "limit": 10, "project_id": project_id}),
                source.query("architecture", {"query": query, "limit": 1, "project_id": project_id}),
                return_exceptions=True,
            )
            files = []
            for r in results:
                if not isinstance(r, Exception) and r.success:
                    meta = r.metadata or {}
                    files.extend(meta.get("files", []))
            return {
                "query": query,
                "explain": results[0].content if not isinstance(results[0], Exception) and results[0].success else None,
                "search_results": results[1].content if not isinstance(results[1], Exception) and results[1].success else None,
                "architecture": results[2].content if not isinstance(results[2], Exception) and results[2].success else None,
                "files": list(set(files))[:20],
            }
        except Exception as e:
            logger.warning("AGENT: RIP context gathering failed - %s", e)
            return {"query": query, "error": str(e), "files": []}

    async def _run_verification(self, changes: list[dict], ctx: dict) -> dict:
        import subprocess
        modified_files = list(set(c["params"]["path"] for c in changes if c["tool"] in ("write_file", "apply_patch")))
        if not modified_files:
            return {"ran": False, "reason": "No files modified"}
        
        results = {}
        for f in modified_files[:5]:
            ext = Path(f).suffix
            cmd = None
            if ext == ".py":
                cmd = f"python -m py_compile {f}"
            elif ext in (".js", ".ts"):
                cmd = f"npx eslint {f} --quiet 2>&1 || true"
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=ctx.get("project_root"))
                results[f] = {"ok": r.returncode == 0, "stdout": r.stdout[:500], "stderr": r.stderr[:500]}
            except Exception as e:
                results[f] = {"ok": False, "error": str(e)}
        return {"ran": True, "results": results}


_agent_runtime = AgentRuntime()

def get_agent_runtime() -> AgentRuntime:
    return _agent_runtime
