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
from gateway.core.agent.planner import ExecutionPlanner, ExecutionPlan, Subtask, SubtaskStatus, get_execution_planner
from gateway.core.agent.recovery import RecoveryEngine, RecoveryPlan, get_recovery_engine
from gateway.core.agent.memory import ExecutionMemory, get_execution_memory
from gateway.core.events import get_event_bus
from gateway.core.events.pipeline import get_pipeline_event_bus
from gateway.core.llm_pool.router import LLMConfig
from gateway.core.sources.rip_client import RIPSource
from gateway.core.planner.engine import PlannerEngine as GatewayPlanner
from gateway.core.planner.budget import allocate_token_budget
from gateway.core.tokenizer.counter import get_token_counter
from gateway.core.classifier.engine import ClassifierEngine
from gateway.core.classifier.models import ClassificationResult, IntentType
from gateway.config import settings
from gateway.storage.database import async_session_factory

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = 'You are a coding agent. Use tools: read_file, search_codebase, trace_dependencies, write_file, apply_patch, run_command, list_directory, finish. Output ONLY JSON: {"tool":"name","params":{...}} or {"tool":"finish","params":{"summary":"..."}}'


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
    VERIFY_EVERY_N_EDITS = 5
    APPROVAL_TIMEOUT_SECONDS = 300
    MAX_CONTEXT_TOKENS = 2000

    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.llm_interface = LLMInterface()
        self.event_bus = get_event_bus()
        self.pipeline_bus = get_pipeline_event_bus()
        self.planner = get_execution_planner()
        self.recovery = get_recovery_engine()
        self.memory = get_execution_memory()
        self.gateway_planner = GatewayPlanner()
        self.classifier = ClassifierEngine()
        self.token_counter = get_token_counter()
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        from gateway.core.agent.tools import ToolDefinition

        self.tool_registry.register(ToolDefinition(
            name="read_file",
            description="Read a file. Returns content.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            handler=self._tool_read_file,
        ))
        self.tool_registry.register(ToolDefinition(
            name="search_codebase",
            description="Search codebase for files and symbols.",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            handler=self._tool_search,
        ))
        self.tool_registry.register(ToolDefinition(
            name="trace_dependencies",
            description="Trace callers and callees of a symbol.",
            parameters={"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
            handler=self._tool_trace,
        ))
        self.tool_registry.register(ToolDefinition(
            name="write_file",
            description="Write content to a file.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
            handler=self._tool_write_file, requires_approval=True, risk_level="medium",
        ))
        self.tool_registry.register(ToolDefinition(
            name="apply_patch",
            description="Apply a unified diff patch to a file.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}, "diff": {"type": "string"}}, "required": ["path", "diff"]},
            handler=self._tool_apply_patch, requires_approval=True, risk_level="medium",
        ))
        self.tool_registry.register(ToolDefinition(
            name="run_command",
            description="Run a shell command.",
            parameters={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            handler=self._tool_run_command, risk_level="low",
        ))
        self.tool_registry.register(ToolDefinition(
            name="list_directory",
            description="List directory contents.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string", "default": "*"}}, "required": ["path"]},
            handler=self._tool_list_dir,
        ))
        self.tool_registry.register(ToolDefinition(
            name="finish",
            description="Signal task completion.",
            parameters={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
            handler=self._tool_finish,
        ))

    # -- Tool Handlers --

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
            return ToolResult(ok=True, output={"content": content[:3000], "lines": content.count(chr(10)) + 1, "size_bytes": os.path.getsize(full)})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_search(self, params: dict, ctx: dict) -> ToolResult:
        try:
            source = RIPSource()
            result = await source.query("search", {"query": params["query"], "limit": 5, "project_id": ctx.get("project_id")})
            return ToolResult(ok=result.success, output={"content": str(result.content)[:800], "metadata": result.metadata})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_trace(self, params: dict, ctx: dict) -> ToolResult:
        try:
            source = RIPSource()
            result = await source.query("trace", {"query": params["symbol"], "project_id": ctx.get("project_id")})
            return ToolResult(ok=result.success, output={"content": str(result.content)[:800], "metadata": result.metadata})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_write_file(self, params: dict, ctx: dict) -> ToolResult:
        import os
        path, content = str(params["path"]), str(params["content"])
        base = ctx.get("project_root", os.getcwd())
        full = os.path.normpath(os.path.join(base, path))
        if not full.startswith(os.path.normpath(base)):
            return ToolResult(ok=False, error=f"Path traversal denied: {path}")
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            existed = os.path.exists(full)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(ok=True, output={"path": full, "size_bytes": os.path.getsize(full), "created": not existed})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_apply_patch(self, params: dict, ctx: dict) -> ToolResult:
        import os, shutil
        path, diff = str(params["path"]), str(params["diff"])
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
                return ToolResult(ok=False, error="Failed to apply diff")
            with open(full, "w", encoding="utf-8") as f:
                f.write(patched)
            return ToolResult(ok=True, output={"path": full, "backup": backup, "lines_before": original.count(chr(10)), "lines_after": patched.count(chr(10))})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    def _apply_unified_diff(self, original: str, diff: str) -> str | None:
        orig_lines = original.splitlines(keepends=True)
        hunks = re.findall(r'@@ -(\d+),?\d* \+(\d+),?\d* @@(.*?)(?=@@|\Z)', diff, re.DOTALL)
        if not hunks:
            return None
        result = list(orig_lines)
        for hunk in hunks:
            orig_start = int(hunk[0]) - 1
            hunk_lines = hunk[2].strip().split('\n')
            i, new_hunk = orig_start, []
            for line in hunk_lines:
                if line.startswith(' '):
                    if i < len(orig_lines): new_hunk.append(orig_lines[i])
                    i += 1
                elif line.startswith('-'):
                    i += 1
                elif line.startswith('+'):
                    new_hunk.append(line[1:] + '\n')
            result = result[:orig_start] + new_hunk + result[orig_start + (i - orig_start):]
        return ''.join(result)

    async def _tool_run_command(self, params: dict, ctx: dict) -> ToolResult:
        import subprocess
        try:
            result = subprocess.run(params["command"], shell=True, capture_output=True, text=True, timeout=60, cwd=ctx.get("project_root"))
            return ToolResult(ok=result.returncode == 0, output={"stdout": result.stdout[-2000:], "stderr": result.stderr[-500:], "exit_code": result.returncode})
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, error="Command timed out")
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_list_dir(self, params: dict, ctx: dict) -> ToolResult:
        import os, glob as globmod
        path, pattern = str(params["path"]), params.get("pattern", "*")
        base = ctx.get("project_root", os.getcwd())
        full = os.path.normpath(os.path.join(base, path))
        if not full.startswith(os.path.normpath(base)):
            return ToolResult(ok=False, error=f"Path traversal denied: {path}")
        try:
            files = [{"name": os.path.relpath(m, full), "is_directory": os.path.isdir(m), "size_bytes": os.path.getsize(m) if not os.path.isdir(m) else 0} for m in globmod.iglob(os.path.join(full, pattern))]
            return ToolResult(ok=True, output={"files": files[:30], "count": len(files)})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_finish(self, params: dict, ctx: dict) -> ToolResult:
        return ToolResult(ok=True, output={"summary": params.get("summary", "Done."), "finished": True})

    # -- Execute --

    async def execute(self, query: str, llm_config: LLMConfig, project_id: str, user_id: str, project_root: str = None) -> AgentResult:
        start_time = time.monotonic()
        ctx = {"project_id": project_id, "user_id": user_id, "project_root": project_root or str(Path.cwd())}
        run_id = str(uuid4())

        logger.info("AGENT: Starting - query=%s", query[:100])
        await self._emit_progress(run_id, "started", "Planning...", query)

        rip_context = await self._gather_budgeted_context(query, project_id, self.MAX_CONTEXT_TOKENS)
        memory_context = self.memory.get_context(project_id)
        plan = await self.planner.plan(query, rip_context, llm_config)

        await self._emit_progress(run_id, "planned", f"{len(plan.subtasks)} subtasks", query)

        all_steps, all_changes, tokens_total = [], [], 0
        final_summary, status = "", "completed"
        self.recovery.reset()

        try:
            while not plan.is_complete:
                ready = plan.ready_subtasks
                if not ready and any(s.status == SubtaskStatus.PENDING for s in plan.subtasks):
                    for p in [s for s in plan.subtasks if s.status == SubtaskStatus.PENDING]:
                        p.status, p.error = SubtaskStatus.FAILED, f"Deadlock: depends on {p.depends_on}"
                    break
                if not ready:
                    break

                for subtask in ready:
                    subtask.status = SubtaskStatus.RUNNING
                    await self._emit_progress(run_id, "subtask_start", subtask.title, query)

                    budgeted_rip = self._trim_context_to_budget(rip_context, 800)
                    steps, changes, tokens, sub_summary, sub_status, sub_error = await self._execute_subtask(
                        subtask, budgeted_rip, memory_context, llm_config, ctx, run_id
                    )

                    all_steps.extend(steps)
                    all_changes.extend(changes)
                    tokens_total += tokens
                    subtask.result_summary = sub_summary

                    if sub_status == "completed":
                        subtask.status = SubtaskStatus.COMPLETED
                        await self._emit_progress(run_id, "subtask_done", f"Done: {subtask.title}", query)
                    else:
                        subtask.status = SubtaskStatus.FAILED
                        subtask.error = sub_error
                        await self._emit_progress(run_id, "subtask_failed", f"Failed: {subtask.title}", query)

            if plan.has_failures:
                status = "partial"
                completed = len([s for s in plan.subtasks if s.status == SubtaskStatus.COMPLETED])
                failed = [s.title for s in plan.subtasks if s.status == SubtaskStatus.FAILED]
                final_summary = f"Completed {completed}/{len(plan.subtasks)} subtasks. Failed: {', '.join(failed[:3])}"
            else:
                final_summary = f"All {len(plan.subtasks)} subtasks completed. {len(all_changes)} files changed."

        except Exception as e:
            logger.error("AGENT: Failed - %s", e)
            status, final_summary = "failed", str(e)[:200]

        verification = await self._run_verification(all_changes, ctx) if all_changes else None
        duration = time.monotonic() - start_time

        await self._emit_progress(run_id, "completed", final_summary, query)
        return AgentResult(query=query, steps=all_steps, changes_made=all_changes, verification=verification, summary=final_summary, tokens_total=tokens_total, duration_seconds=duration, status=status)

    async def _classify_task(self, query: str) -> ClassificationResult:
        try:
            return await asyncio.get_event_loop().run_in_executor(None, lambda: self.classifier.classify(query))
        except Exception:
            return ClassificationResult(intent=IntentType.INVESTIGATION, confidence=0.5, domain="general", risk_level="low", strategy="rules", domain_keywords_found=[], raw_task=query)

    async def _gather_budgeted_context(self, query: str, project_id: str, token_budget: int) -> dict:
        try:
            source = RIPSource()
            result = await source.query("explain", {"query": query, "limit": 2, "project_id": project_id})
            context = {"query": query, "explain": str(result.content)[:token_budget] if result.success else "", "files": (result.metadata or {}).get("files", [])[:5]}
            return context
        except Exception as e:
            return {"query": query, "error": str(e)[:200], "files": []}

    def _trim_context_to_budget(self, context: dict, max_tokens: int) -> dict:
        trimmed = dict(context)
        if trimmed.get("explain"):
            while self.token_counter.count(json.dumps(trimmed)) > max_tokens and len(str(trimmed.get("explain", ""))) > 50:
                trimmed["explain"] = str(trimmed["explain"])[:int(len(str(trimmed["explain"])) * 0.7)]
        while self.token_counter.count(json.dumps(trimmed)) > max_tokens and len(trimmed.get("files", [])) > 1:
            trimmed["files"] = trimmed["files"][:max(1, len(trimmed["files"]) - 1)]
        return trimmed

    async def _execute_subtask(self, subtask, rip_context, memory_context, llm_config, ctx, run_id):
        tools_desc = self.tool_registry.get_for_llm()
        system_prompt = AGENT_SYSTEM_PROMPT

        context_str = json.dumps({"task": subtask.description, "files": rip_context.get("files", [])[:3], "context": str(rip_context.get("explain", ""))[:300]})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {subtask.title}\nContext: {context_str}\nStart by reading relevant files or listing directories."}
        ]

        steps, changes, tokens_total = [], [], 0
        final_summary, status, error = "", "completed", None

        try:
            for turn in range(min(subtask.estimated_turns + 3, 10)):
                await self._emit_progress(run_id, "turn", f"Turn {turn + 1}", subtask.title)

                response = await self.llm_interface.call_with_tools(messages, tools_desc, llm_config)
                tokens_total += response.tokens_used

                if response.type == ResponseType.TEXT:
                    steps.append(AgentStep(turn=turn+1, tool_name=None, tool_params=None, tool_result=None, llm_response=str(response.text)[:300], tokens_used=response.tokens_used, timestamp=datetime.now(UTC).isoformat()))
                    messages.append({"role": "assistant", "content": str(response.raw)[:500]})
                    continue

                if response.type == ResponseType.TOOL_CALL:
                    tool_name = response.tool_name or ""
                    tool_params = response.tool_params or {}
                    tool = self.tool_registry.get(tool_name)

                    if not tool:
                        result = ToolResult(ok=False, error=f"Unknown tool: {tool_name}")
                    elif tool.requires_approval:
                        approved = await self._request_approval(run_id, tool_name, tool_params)
                        result = await tool.handler(tool_params, ctx) if approved else ToolResult(ok=False, error="Approval denied")
                    else:
                        result = await tool.handler(tool_params, ctx)

                    steps.append(AgentStep(turn=turn+1, tool_name=tool_name, tool_params=tool_params, tool_result={"ok": result.ok, "output": str(result.output)[:300] if result.output else None, "error": result.error}, llm_response=str(response.raw)[:300], tokens_used=response.tokens_used, timestamp=datetime.now(UTC).isoformat()))
                    messages.append({"role": "assistant", "content": str(response.raw)[:300]})
                    messages.append({"role": "user", "content": f"Result: {'OK' if result.ok else 'Error: ' + str(result.error)[:100]}"})

                    if tool_name in ("write_file", "apply_patch") and result.ok:
                        changes.append({"tool": tool_name, "params": tool_params, "result": str(result.output)[:200]})

                    if tool_name == "finish":
                        final_summary = str(tool_params.get("summary", "Done."))
                        break
                    continue

                if response.type == ResponseType.FINISH:
                    final_summary = str(response.finish_summary or "Done.")
                    break
            else:
                final_summary = "Completed after max turns."

        except Exception as e:
            logger.error("AGENT: Subtask failed: %s", e)
            status, error = "failed", str(e)[:200]

        return steps, changes, tokens_total, final_summary, status, error

    async def _request_approval(self, run_id, tool_name, params):
        event = asyncio.Event()
        self._pending_approvals[run_id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=self.APPROVAL_TIMEOUT_SECONDS)
            return self._approval_results.get(run_id, False)
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending_approvals.pop(run_id, None)
            self._approval_results.pop(run_id, None)

    def approve_tool(self, run_id, approved):
        self._approval_results[run_id] = approved
        if run_id in self._pending_approvals:
            self._pending_approvals[run_id].set()

    async def _emit_progress(self, run_id, stage, detail, query, meta=None):
        try:
            await self.pipeline_bus.emit(run_id, stage=stage, status="ok", detail=detail, source="agent", meta=meta or {})
        except Exception:
            pass

    async def _run_verification(self, changes, ctx):
        import subprocess
        modified = list(set(c["params"]["path"] for c in changes if c["tool"] in ("write_file", "apply_patch")))
        if not modified:
            return {"ran": False}
        results = {}
        for f in modified[:5]:
            ext = Path(f).suffix
            cmd = None
            if ext == ".py": cmd = f"python -m py_compile {f}"
            elif ext in (".js", ".ts"): cmd = f"npx eslint {f} --quiet 2>&1 || true"
            if cmd:
                try:
                    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=ctx.get("project_root"))
                    results[f] = {"ok": r.returncode == 0, "stderr": r.stderr[:300]}
                except Exception as e:
                    results[f] = {"ok": False, "error": str(e)[:200]}
        return {"ran": True, "results": results}


_agent_runtime = AgentRuntime()

def get_agent_runtime() -> AgentRuntime:
    return _agent_runtime
