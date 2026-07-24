"""Terminal Session — PTY + WebSocket streaming for real-time terminal I/O."""
from __future__ import annotations
import asyncio, json, logging, time
from datetime import UTC, datetime
from uuid import uuid4
from gateway.core.sandbox.orchestrator import get_orchestrator
from gateway.core.sandbox.security import get_security_policy, CommandRisk
from gateway.core.events.pipeline import get_pipeline_event_bus
from gateway.core.workspace.memory import get_workspace_memory

logger = logging.getLogger(__name__)

class TerminalSession:
    def __init__(self, sandbox_id: str, session_id: str, user_id: str, project_id: str):
        self.terminal_id = str(uuid4())
        self.sandbox_id = sandbox_id
        self.session_id = session_id
        self.user_id = user_id
        self.project_id = project_id
        self.created_at = datetime.now(UTC)
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._output_queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._subscribers: list[asyncio.Queue[dict]] = []
        self._security = get_security_policy()
        self._orchestrator = get_orchestrator()
        self._event_bus = get_pipeline_event_bus()
        self._workspace_memory = get_workspace_memory()
        self._command_history: list[dict] = []

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._process_loop())
        logger.info("Terminal started: %s (sandbox=%s)", self.terminal_id, self.sandbox_id)

    async def stop(self) -> None:
        self._running = False
        await self._broadcast({"type": "terminal_closed", "terminal_id": self.terminal_id})
        logger.info("Terminal stopped: %s", self.terminal_id)

    async def write(self, data: str) -> None:
        await self._input_queue.put(data)

    async def subscribe(self) -> asyncio.Queue[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        if queue in self._subscribers: self._subscribers.remove(queue)

    async def _process_loop(self) -> None:
        while self._running:
            try:
                command = await asyncio.wait_for(self._input_queue.get(), timeout=1.0)
                await self._execute_command(command.strip())
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Terminal process error: %s", e)
                await self._broadcast({"type": "error", "message": str(e)})

    async def _execute_command(self, command: str) -> None:
        if not command: return
        allowed, reason, risk = self._security.validate_command(command)
        sanitized = self._security.sanitize_for_logging(command)

        await self._broadcast({"type": "command_start", "command": sanitized, "risk": risk.value})

        if not allowed:
            await self._broadcast({"type": "command_blocked", "command": sanitized, "reason": reason})
            return

        if self._security.needs_approval(risk):
            await self._broadcast({"type": "approval_needed", "command": sanitized, "reason": reason, "risk": risk.value})
            return

        await self._run_command(command, sanitized)

    async def execute_approved_command(self, command: str) -> None:
        sanitized = self._security.sanitize_for_logging(command)
        await self._run_command(command, sanitized)

    async def _run_command(self, command: str, sanitized: str) -> None:
        start_time = time.time()
        try:
            exit_code, output = await asyncio.to_thread(self._orchestrator.exec_command, self.sandbox_id, command)
            duration_ms = int((time.time() - start_time) * 1000)

            await self._broadcast({"type": "command_output", "command": sanitized, "output": output, "exit_code": exit_code, "duration_ms": duration_ms})

            record = {"command": sanitized, "exit_code": exit_code, "output_preview": output[:200], "duration_ms": duration_ms, "timestamp": datetime.now(UTC).isoformat()}
            self._command_history.append(record)

            await self._event_bus.emit(self.session_id, stage="sandbox_command", status="done" if exit_code == 0 else "failed", detail=f"{sanitized[:80]} (exit {exit_code})", source="sandbox", meta={"command": sanitized, "exit_code": exit_code, "duration_ms": duration_ms})

            try:
                await self._workspace_memory.record(workspace_id=self.project_id, project_id=self.project_id, category="sandbox_command", query=sanitized, summary=f"Exit {exit_code} in {duration_ms}ms", status="completed" if exit_code == 0 else "failed", created_by=self.user_id)
            except Exception: pass

        except Exception as e:
            await self._broadcast({"type": "command_error", "command": sanitized, "error": str(e)})

    async def _broadcast(self, message: dict) -> None:
        message["terminal_id"] = self.terminal_id
        message["timestamp"] = datetime.now(UTC).isoformat()
        for queue in self._subscribers:
            try: queue.put_nowait(message)
            except asyncio.QueueFull: pass

    def get_history(self) -> list[dict]: return self._command_history

class TerminalManager:
    def __init__(self): self._terminals: dict[str, TerminalSession] = {}
    def create_terminal(self, sandbox_id: str, session_id: str, user_id: str, project_id: str) -> TerminalSession:
        t = TerminalSession(sandbox_id, session_id, user_id, project_id); self._terminals[t.terminal_id] = t; return t
    def get_terminal(self, terminal_id: str) -> TerminalSession | None: return self._terminals.get(terminal_id)
    def remove_terminal(self, terminal_id: str) -> None: self._terminals.pop(terminal_id, None)
    def get_active_count(self) -> int: return len(self._terminals)

_terminal_manager: TerminalManager | None = None
def get_terminal_manager() -> TerminalManager:
    global _terminal_manager
    if _terminal_manager is None: _terminal_manager = TerminalManager()
    return _terminal_manager
