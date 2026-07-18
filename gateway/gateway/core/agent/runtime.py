"""Gateway-controlled Agent Runtime. The LLM reasons, the Gateway executes."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
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
from core.projects import get_project
from core.storage.database import async_session_factory as core_async_session_factory

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


RunStateCallback = Callable[[str, dict[str, Any]], Any]


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
        self._pending_approval_details: dict[str, dict[str, Any]] = {}
        self._active_write_paths: dict[str, set[str]] = {}
        self._write_path_guard = asyncio.Lock()
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
            handler=self._tool_run_command, risk_level="medium",
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

    def _resolve_safe_path(self, path: str, ctx: dict, *, must_exist: bool = False) -> tuple[Path | None, str | None]:
        base = Path(str(ctx.get("project_root") or os.getcwd())).resolve()
        full = (base / path).resolve()
        try:
            full.relative_to(base)
        except ValueError:
            return None, f"Path traversal denied: {path}"
        if must_exist and not full.exists():
            return None, f"File not found: {path}"
        return full, None

    async def _tool_read_file(self, params: dict, ctx: dict) -> ToolResult:
        path = str(params["path"])
        full, error = self._resolve_safe_path(path, ctx, must_exist=True)
        if error or full is None:
            return ToolResult(ok=False, error=error)
        try:
            with full.open("r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return ToolResult(ok=True, output={"content": content[:3000], "lines": content.count(chr(10)) + 1, "size_bytes": full.stat().st_size})
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
        path, content = str(params["path"]), str(params["content"])
        full, error = self._resolve_safe_path(path, ctx)
        if error or full is None:
            return ToolResult(ok=False, error=error)
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            existed = full.exists()
            backup = str(full) + ".orig"
            if existed and not Path(backup).exists():
                shutil.copy2(full, backup)
            with full.open("w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(ok=True, output={"path": str(full), "backup": backup if existed else None, "size_bytes": full.stat().st_size, "created": not existed})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_apply_patch(self, params: dict, ctx: dict) -> ToolResult:
        path, diff = str(params["path"]), str(params["diff"])
        full, error = self._resolve_safe_path(path, ctx, must_exist=True)
        if error or full is None:
            return ToolResult(ok=False, error=error)
        try:
            backup = str(full) + ".orig"
            if not Path(backup).exists():
                shutil.copy2(full, backup)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False, encoding="utf-8") as patch_file:
                patch_file.write(diff)
                patch_path = patch_file.name
            try:
                check = subprocess.run(["git", "apply", "--check", patch_path], cwd=ctx.get("project_root"), capture_output=True, text=True, timeout=30)
                if check.returncode != 0:
                    return ToolResult(ok=False, error=f"Patch does not apply cleanly: {check.stderr[:300]}")
                applied = subprocess.run(["git", "apply", patch_path], cwd=ctx.get("project_root"), capture_output=True, text=True, timeout=30)
                if applied.returncode != 0:
                    return ToolResult(ok=False, error=f"Patch apply failed: {applied.stderr[:300]}")
                return ToolResult(ok=True, output={"path": str(full), "backup": backup})
            finally:
                try:
                    os.unlink(patch_path)
                except OSError:
                    pass
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_run_command(self, params: dict, ctx: dict) -> ToolResult:
        try:
            result = subprocess.run(params["command"], shell=True, capture_output=True, text=True, timeout=60, cwd=ctx.get("project_root"))
            return ToolResult(ok=result.returncode == 0, output={"stdout": result.stdout[-2000:], "stderr": result.stderr[-500:], "exit_code": result.returncode})
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, error="Command timed out")
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_list_dir(self, params: dict, ctx: dict) -> ToolResult:
        import glob as globmod
        path, pattern = str(params["path"]), params.get("pattern", "*")
        full, error = self._resolve_safe_path(path, ctx, must_exist=True)
        if error or full is None:
            return ToolResult(ok=False, error=error)
        try:
            files = [{"name": os.path.relpath(m, full), "is_directory": os.path.isdir(m), "size_bytes": os.path.getsize(m) if not os.path.isdir(m) else 0} for m in globmod.iglob(os.path.join(str(full), pattern))]
            return ToolResult(ok=True, output={"files": files[:30], "count": len(files)})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    async def _tool_finish(self, params: dict, ctx: dict) -> ToolResult:
        return ToolResult(ok=True, output={"summary": params.get("summary", "Done."), "finished": True})

    # -- Execute --

    async def execute(
        self,
        query: str,
        llm_config: LLMConfig,
        project_id: str | None,
        user_id: str,
        project_root: str | None = None,
        run_id: str | None = None,
        on_state_change: RunStateCallback | None = None,
    ) -> AgentResult:
        start_time = time.monotonic()
        run_id = run_id or str(uuid4())
        resolved_root, root_error = await self._resolve_project_root(project_id, project_root)
        if root_error or resolved_root is None:
            summary = root_error or "No indexed root found for project_id"
            await self._emit_progress(run_id, "failed", summary, query, {"project_id": project_id})
            await self._notify_run_state(on_state_change, run_id, {"status": "failed", "error": summary, "summary": summary})
            return AgentResult(query=query, steps=[], changes_made=[], verification=None, summary=summary, tokens_total=0, duration_seconds=0, status="failed", error=summary)

        ctx = {"project_id": project_id, "user_id": user_id, "project_root": resolved_root}

        logger.info("AGENT: Starting - query=%s", query[:100])
        await self._emit_progress(run_id, "started", "Planning...", query)
        await self._notify_run_state(on_state_change, run_id, {"status": "running", "query": query, "steps": [], "changes_made": [], "project_id": project_id, "project_root": resolved_root})

        rip_context = await self._gather_budgeted_context(query, project_id, self.MAX_CONTEXT_TOKENS)
        memory_context = self.memory.get_context(project_id) if project_id else ""
        plan = await self.planner.plan(query, rip_context, llm_config)

        await self._emit_progress(run_id, "planned", f"{len(plan.subtasks)} subtasks", query)
        await self._notify_run_state(on_state_change, run_id, {"status": "running", "plan": [asdict(s) for s in plan.subtasks]})

        all_steps, all_changes, tokens_total = [], [], 0
        final_summary, status = "", "completed"
        self.recovery.reset()
        self._active_write_paths[run_id] = set()

        try:
            while not plan.is_complete:
                ready = plan.ready_subtasks
                if not ready and any(s.status == SubtaskStatus.PENDING for s in plan.subtasks):
                    for p in [s for s in plan.subtasks if s.status == SubtaskStatus.PENDING]:
                        p.status, p.error = SubtaskStatus.FAILED, f"Deadlock: depends on {p.depends_on}"
                    break
                if not ready:
                    break

                results = await asyncio.gather(
                    *[
                        self._execute_ready_subtask(
                            subtask, rip_context, memory_context, llm_config, ctx, run_id, query, on_state_change
                        )
                        for subtask in ready
                    ],
                    return_exceptions=True,
                )

                for subtask, result in zip(ready, results):
                    if isinstance(result, Exception):
                        subtask.status = SubtaskStatus.FAILED
                        subtask.error = str(result)[:200]
                        await self._emit_progress(run_id, "subtask_failed", f"Failed: {subtask.title}", query, {"subtask_id": subtask.id, "error": subtask.error})
                        await self._notify_run_state(on_state_change, run_id, {"status": "running", "plan": [asdict(s) for s in plan.subtasks]})
                        continue
                    steps, changes, tokens, sub_summary, sub_status, sub_error = result
                    all_steps.extend(steps)
                    all_changes.extend(changes)
                    tokens_total += tokens
                    await self._notify_run_state(on_state_change, run_id, {
                        "status": "running",
                        "steps": [asdict(s) for s in all_steps],
                        "changes_made": all_changes,
                        "tokens_total": tokens_total,
                        "plan": [asdict(s) for s in plan.subtasks],
                    })

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
        finally:
            self._active_write_paths.pop(run_id, None)

        verification = await self._run_verification(all_changes, ctx) if all_changes else None
        duration = time.monotonic() - start_time

        await self._emit_progress(run_id, "completed", final_summary, query)
        result = AgentResult(query=query, steps=all_steps, changes_made=all_changes, verification=verification, summary=final_summary, tokens_total=tokens_total, duration_seconds=duration, status=status)
        await self._notify_run_state(on_state_change, run_id, {
            "status": result.status,
            "query": query,
            "steps": [asdict(s) for s in all_steps],
            "changes_made": all_changes,
            "verification": verification,
            "summary": final_summary,
            "tokens_total": tokens_total,
            "duration_seconds": duration,
            "error": result.error,
            "pending_approval": None,
        })
        return result

    async def _resolve_project_root(self, project_id: str | None, explicit_root: str | None) -> tuple[str | None, str | None]:
        if explicit_root:
            root = Path(explicit_root).expanduser().resolve()
            if root.exists() and root.is_dir():
                return str(root), None
            return None, f"Project root does not exist: {explicit_root}"

        if not project_id:
            return None, "Agent execution requires project_id so file tools are scoped to one indexed project"

        try:
            async with core_async_session_factory() as session:
                project = await get_project(session, project_id)
        except Exception as e:
            return None, f"Could not resolve project_id {project_id}: {str(e)[:200]}"

        if project is None or not project.root:
            return None, f"No indexed root found for project_id {project_id}"
        root = Path(project.root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            return None, f"Indexed root is unavailable for project_id {project_id}: {project.root}"
        return str(root), None

    async def _notify_run_state(self, callback: RunStateCallback | None, run_id: str, updates: dict[str, Any]) -> None:
        if callback is None:
            return
        try:
            maybe = callback(run_id, updates)
            if inspect.isawaitable(maybe):
                await maybe
        except Exception:
            logger.debug("AGENT: run state callback failed", exc_info=True)

    async def _execute_ready_subtask(self, subtask, rip_context, memory_context, llm_config, ctx, run_id, query, on_state_change):
        subtask.status = SubtaskStatus.RUNNING
        await self._emit_progress(run_id, "subtask_start", subtask.title, query, {"subtask_id": subtask.id})
        await self._notify_run_state(on_state_change, run_id, {"status": "running", "current_subtask": asdict(subtask)})

        budgeted_rip = self._trim_context_to_budget(rip_context, 800)
        steps, changes, tokens, sub_summary, sub_status, sub_error = await self._execute_subtask(
            subtask, budgeted_rip, memory_context, llm_config, ctx, run_id, on_state_change
        )
        subtask.result_summary = sub_summary

        if sub_status == "completed":
            subtask.status = SubtaskStatus.COMPLETED
            await self._emit_progress(run_id, "subtask_done", f"Done: {subtask.title}", query, {"subtask_id": subtask.id})
        else:
            subtask.status = SubtaskStatus.FAILED
            subtask.error = sub_error
            await self._emit_progress(run_id, "subtask_failed", f"Failed: {subtask.title}", query, {"subtask_id": subtask.id, "error": sub_error})

        return steps, changes, tokens, sub_summary, sub_status, sub_error

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

    async def _execute_subtask(self, subtask, rip_context, memory_context, llm_config, ctx, run_id, on_state_change: RunStateCallback | None = None):
        tools_desc = self.tool_registry.get_for_llm()
        system_prompt = AGENT_SYSTEM_PROMPT

        context_str = json.dumps({"task": subtask.description, "files": rip_context.get("files", [])[:3], "context": str(rip_context.get("explain", ""))[:300]})
        memory_note = f"\nExecution memory for this project:\n{memory_context}" if memory_context else ""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {subtask.title}\nContext: {context_str}{memory_note}\nStart by reading relevant files or listing directories."}
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
                    else:
                        result = await self._execute_tool(tool, tool_name, tool_params, ctx, run_id, subtask.id, on_state_change)

                    steps.append(AgentStep(turn=turn+1, tool_name=tool_name, tool_params=tool_params, tool_result={"ok": result.ok, "output": str(result.output)[:300] if result.output else None, "error": result.error}, llm_response=str(response.raw)[:300], tokens_used=response.tokens_used, timestamp=datetime.now(UTC).isoformat()))
                    messages.append({"role": "assistant", "content": str(response.raw)[:300]})

                    if tool_name in ("write_file", "apply_patch"):
                        self._record_memory(ctx, tool_params, result, tool_name)

                    if not result.ok:
                        recovery_message = await self._recovery_message(
                            subtask=subtask,
                            turn=turn,
                            tool_name=tool_name,
                            tool_params=tool_params,
                            result=result,
                            steps=steps,
                            ctx=ctx,
                            llm_config=llm_config,
                            run_id=run_id,
                        )
                        messages.append({"role": "user", "content": recovery_message})
                    else:
                        messages.append({"role": "user", "content": "Result: OK"})

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

    async def _execute_tool(self, tool, tool_name: str, tool_params: dict, ctx: dict, run_id: str, subtask_id: str, on_state_change: RunStateCallback | None) -> ToolResult:
        await self._emit_progress(run_id, "tool_start", f"{tool_name}", "", {"tool": tool_name, "params": self._safe_tool_params(tool_params), "subtask_id": subtask_id})
        await self._notify_run_state(on_state_change, run_id, {"status": "running", "last_tool": {"tool": tool_name, "params": self._safe_tool_params(tool_params), "subtask_id": subtask_id}})

        requires_approval = tool.requires_approval or (tool_name == "run_command" and not self._is_allowlisted_command(str(tool_params.get("command", ""))))
        if requires_approval:
            approved = await self._request_approval(run_id, tool_name, tool_params, on_state_change)
            if not approved:
                return ToolResult(ok=False, error="Approval denied")

        if tool_name in ("write_file", "apply_patch"):
            path = str(tool_params.get("path", ""))
            full, error = self._resolve_safe_path(path, ctx)
            if error or full is None:
                return ToolResult(ok=False, error=error)
            active_path = str(full)
            async with self._write_path_guard:
                active = self._active_write_paths.setdefault(run_id, set())
                if active_path in active:
                    return ToolResult(ok=False, error=f"Concurrent write collision denied: {path}")
                active.add(active_path)
            try:
                result = await tool.handler(tool_params, ctx)
            finally:
                async with self._write_path_guard:
                    self._active_write_paths.get(run_id, set()).discard(active_path)
        else:
            result = await tool.handler(tool_params, ctx)

        await self._emit_progress(
            run_id,
            "tool_done" if result.ok else "tool_failed",
            f"{tool_name}: {'ok' if result.ok else result.error}",
            "",
            {"tool": tool_name, "ok": result.ok, "subtask_id": subtask_id},
        )
        return result

    def _safe_tool_params(self, params: dict) -> dict:
        safe = dict(params)
        if "content" in safe:
            safe["content"] = f"<{len(str(safe['content']))} chars>"
        if "diff" in safe:
            safe["diff"] = f"<{len(str(safe['diff']))} chars>"
        return safe

    def _record_memory(self, ctx: dict, tool_params: dict, result: ToolResult, tool_name: str) -> None:
        project_id = ctx.get("project_id")
        if not project_id:
            return
        try:
            self.memory.record_result(
                project_id=str(project_id),
                file_path=str(tool_params.get("path", "")),
                success=result.ok,
                error=result.error,
                tool_name=tool_name,
            )
        except Exception:
            logger.debug("AGENT: memory record failed", exc_info=True)

    async def _recovery_message(self, subtask, turn: int, tool_name: str, tool_params: dict, result: ToolResult, steps: list[AgentStep], ctx: dict, llm_config: LLMConfig, run_id: str) -> str:
        error = result.error or "unknown error"
        recovery_plan = await self.recovery.attempt_recovery(
            step_id=f"{subtask.id}:{tool_name}",
            tool_name=tool_name,
            error=error,
            original_query=subtask.description,
            recent_context=[{"tool": s.tool_name, "result": s.tool_result} for s in steps[-5:]],
            llm_config=llm_config,
        )
        if recovery_plan is None or not recovery_plan.recoverable:
            explanation = recovery_plan.explanation if recovery_plan else "max retries reached"
            await self._emit_progress(run_id, "recovery_failed", f"{tool_name}: {explanation}", subtask.title, {"tool": tool_name, "subtask_id": subtask.id})
            return f"Result: Error: {error}. Recovery exhausted: {explanation}."

        await self._emit_progress(run_id, "recovery", f"Retrying {tool_name}: {recovery_plan.recovery_action}", subtask.title, {"tool": tool_name, "subtask_id": subtask.id, "attempt": self.recovery.retry_counts.get(f"{subtask.id}:{tool_name}", 0), "max_attempts": self.recovery.MAX_RETRIES})
        if recovery_plan.should_rollback and tool_name in ("write_file", "apply_patch"):
            rollback = await self._rollback_change(tool_params, ctx)
            await self._emit_progress(run_id, "rollback", rollback.error or "Rollback completed", subtask.title, {"tool": tool_name, "ok": rollback.ok, "subtask_id": subtask.id})
        return (
            f"Result: Error: {error}. Recovery guidance: {recovery_plan.recovery_action}. "
            f"Try: {recovery_plan.alternative_approach}."
        )

    async def _rollback_change(self, params: dict, ctx: dict) -> ToolResult:
        path = str(params.get("path", ""))
        full, error = self._resolve_safe_path(path, ctx)
        if error or full is None:
            return ToolResult(ok=False, error=error)
        backup = Path(str(full) + ".orig")
        if not backup.exists():
            return ToolResult(ok=False, error=f"No rollback backup found for {path}")
        try:
            shutil.copy2(backup, full)
            return ToolResult(ok=True, output={"path": str(full), "backup": str(backup)})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    def _is_allowlisted_command(self, command: str) -> bool:
        try:
            parts = shlex.split(command, posix=False)
        except ValueError:
            return False
        normalized = [p.lower().strip('"') for p in parts]
        allowed_prefixes = [
            ["pytest"],
            ["python", "-m", "py_compile"],
            ["python3", "-m", "py_compile"],
            ["npm", "test"],
            ["npx", "eslint"],
            ["npx", "tsc", "--noemit"],
            ["dart", "analyze"],
            ["ruff", "check"],
            ["go", "build"],
            ["go", "vet"],
            ["cargo", "check"],
        ]
        return any(normalized[:len(prefix)] == prefix for prefix in allowed_prefixes)

    async def _request_approval(self, run_id, tool_name, params, on_state_change: RunStateCallback | None = None):
        event = asyncio.Event()
        self._pending_approvals[run_id] = event
        requested_at = datetime.now(UTC).isoformat()
        details = {"tool_name": tool_name, "params": self._safe_tool_params(params), "requested_at": requested_at, "timeout_seconds": self.APPROVAL_TIMEOUT_SECONDS}
        self._pending_approval_details[run_id] = details
        await self._emit_progress(run_id, "approval_needed", f"Waiting for approval: {tool_name} on {params.get('path') or params.get('command') or ''}", "", details)
        await self._notify_run_state(on_state_change, run_id, {"status": "awaiting_approval", "pending_approval": details})
        try:
            await asyncio.wait_for(event.wait(), timeout=self.APPROVAL_TIMEOUT_SECONDS)
            approved = self._approval_results.get(run_id, False)
            await self._emit_progress(run_id, "approval_granted" if approved else "approval_denied", f"Approval {'granted' if approved else 'denied'} for {tool_name}", "", details)
            await self._notify_run_state(on_state_change, run_id, {"status": "running", "pending_approval": None})
            return approved
        except asyncio.TimeoutError:
            await self._emit_progress(run_id, "approval_timed_out", f"Approval timed out for {tool_name}", "", details)
            await self._notify_run_state(on_state_change, run_id, {"status": "running", "pending_approval": None})
            return False
        finally:
            self._pending_approvals.pop(run_id, None)
            self._approval_results.pop(run_id, None)
            self._pending_approval_details.pop(run_id, None)

    def approve_tool(self, run_id, approved):
        self._approval_results[run_id] = approved
        if run_id in self._pending_approvals:
            self._pending_approvals[run_id].set()

    def pending_approval(self, run_id: str) -> dict[str, Any] | None:
        return self._pending_approval_details.get(run_id)

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
