"""Terminal Session — PTY + WebSocket streaming for real-time terminal I/O."""
from __future__ import annotations
import asyncio, codecs, json, logging, time, re
from datetime import UTC, datetime
from uuid import uuid4
from gateway.core.sandbox.orchestrator import get_orchestrator
from gateway.core.sandbox.security import get_security_policy, CommandRisk
from gateway.core.events.pipeline import get_pipeline_event_bus
from gateway.core.workspace.memory import get_workspace_memory

logger = logging.getLogger(__name__)
END_MARKER = b"\x00__CMD_DONE__\x00"

ANSI_ESCAPE = re.compile(r'''
    \x1B
    (?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])
''', re.VERBOSE)
OSC_ESCAPE = re.compile(r'\x1B\].*?(?:\x07|\x1B\\)')
DCS_ESCAPE = re.compile(r'\x1BP.*?\x1B\\')
OTHER_ESCAPE = re.compile(r'\x1B[PX^_].*?\x1B\\')

def clean_ansi(text: str) -> str:
    text = OSC_ESCAPE.sub('', text)
    text = DCS_ESCAPE.sub('', text)
    text = OTHER_ESCAPE.sub('', text)
    text = ANSI_ESCAPE.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

class TerminalSession:
    def __init__(self, sandbox_id: str, session_id: str, user_id: str, project_id: str):
        self.terminal_id = str(uuid4())
        self.sandbox_id = sandbox_id
        self.session_id = session_id
        self.user_id = user_id
        self.project_id = project_id
        self.created_at = datetime.now(UTC)
        self._input_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._running = False
        self._is_executing = False
        self._persistent_reader = None
        self._persistent_writer = None
        self._reader_task = None
        self._writer_task = None
        self._current_sanitized = ""
        self._current_start_time = 0.0
        self._subscribers: list[asyncio.Queue[dict]] = []
        self._security = get_security_policy()
        self._orchestrator = get_orchestrator()
        self._event_bus = get_pipeline_event_bus()
        self._workspace_memory = get_workspace_memory()
        self._command_history: list[dict] = []

    @property
    def is_executing(self) -> bool:
        return self._is_executing

    async def start(self) -> None:
        self._running = True
        self._writer_task = asyncio.create_task(self._process_loop())
        logger.info("Terminal started: %s (sandbox=%s)", self.terminal_id, self.sandbox_id)

    async def stop(self) -> None:
        self._running = False
        if self._persistent_writer:
            self._persistent_writer.close()
        if self._reader_task:
            self._reader_task.cancel()
        if self._writer_task:
            self._writer_task.cancel()
        await self._broadcast({"type": "terminal_closed", "terminal_id": self.terminal_id})
        logger.info("Terminal stopped: %s", self.terminal_id)

    async def write(self, data: str) -> None:
        if self._is_executing:
            await self._input_queue.put({"type": "input", "text": data})
        else:
            await self._input_queue.put({"type": "command", "text": data})

    async def subscribe(self) -> asyncio.Queue[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        if queue in self._subscribers: self._subscribers.remove(queue)

    async def _process_loop(self) -> None:
        while self._running:
            try:
                msg = await asyncio.wait_for(self._input_queue.get(), timeout=1.0)
                if msg["type"] == "command":
                    await self._execute_command(msg["text"].strip())
                elif msg["type"] == "input":
                    if self._persistent_writer:
                        req = json.dumps({"input": msg["text"]}) + "\n"
                        self._persistent_writer.write(req.encode())
                        await self._persistent_writer.drain()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Terminal process error: %s", e)

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
        await self._run_command(command, self._security.sanitize_for_logging(command))

    async def _run_command(self, command: str, sanitized: str) -> None:
        self._current_start_time = time.time()
        self._current_sanitized = sanitized
        self._is_executing = True
        if self._persistent_writer is None:
            try:
                port = await asyncio.to_thread(self._orchestrator.get_stream_port, self.sandbox_id)
            except Exception:
                await self._run_command_legacy(command, sanitized, self._current_start_time)
                self._is_executing = False
                return
            try:
                self._persistent_reader, self._persistent_writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port), timeout=2.0)
                self._reader_task = asyncio.create_task(self._read_stream())
            except Exception:
                await self._run_command_legacy(command, sanitized, self._current_start_time)
                self._is_executing = False
                return
        try:
            request = json.dumps({"command": command, "workdir": "/workspace"}) + "\n"
            self._persistent_writer.write(request.encode())
            await self._persistent_writer.drain()
        except Exception as e:
            await self._broadcast({"type": "command_error", "command": sanitized, "error": str(e)})
            self._is_executing = False

    async def _read_stream(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        buffer = b""
        full_output_parts: list[str] = []
        try:
            while self._running and self._persistent_reader:
                chunk = await self._persistent_reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                if b"__RIP_PROMPT__" in buffer:
                    parts = buffer.split(b"__RIP_PROMPT__", 1)
                    pre = parts[0]
                    if pre:
                        text = decoder.decode(pre)
                        cleaned = clean_ansi(text)
                        if cleaned.strip():
                            full_output_parts.append(cleaned)
                    output = "".join(full_output_parts)
                    if output.strip():
                        duration_ms = int((time.time() - self._current_start_time) * 1000)
                        await self._broadcast({"type": "command_output", "command": self._current_sanitized, "output": output, "exit_code": 0, "duration_ms": duration_ms})
                    self._is_executing = False
                    full_output_parts.clear()
                    buffer = parts[1] if len(parts) > 1 else b""
                    continue
                if END_MARKER in buffer:
                    pre, _, footer = buffer.partition(END_MARKER)
                    if pre:
                        text = decoder.decode(pre)
                        cleaned = clean_ansi(text)
                        full_output_parts.append(cleaned)
                    try:
                        footer_str = footer.decode("utf-8", errors="replace").strip()
                        footer_json_str = footer_str.split("\n")[0] if "\n" in footer_str else footer_str
                        exit_code = json.loads(footer_json_str).get("exit_code", -1)
                    except Exception:
                        exit_code = -1
                    output = "".join(full_output_parts)
                    duration_ms = int((time.time() - self._current_start_time) * 1000)
                    await self._broadcast({"type": "command_output", "command": self._current_sanitized, "output": output, "exit_code": exit_code, "duration_ms": duration_ms})
                    await self._record_completion(self._current_sanitized, exit_code, output, duration_ms)
                    self._is_executing = False
                    full_output_parts.clear()
                    buffer = b""
                    continue
                text = decoder.decode(buffer, final=False)
                if text:
                    cleaned = clean_ansi(text)
                    full_output_parts.append(cleaned)
                    if cleaned.strip():
                        await self._broadcast({"type": "stream_chunk", "output": cleaned})
                buffer = b""
        except Exception as e:
            logger.error("Stream reader error: %s", e)
        finally:
            self._persistent_reader = None
            self._persistent_writer = None
            self._is_executing = False

    async def _run_command_legacy(self, command: str, sanitized: str, start_time: float) -> None:
        try:
            exit_code, output = await asyncio.to_thread(self._orchestrator.exec_command, self.sandbox_id, command)
            duration_ms = int((time.time() - start_time) * 1000)
            await self._broadcast({"type": "command_output", "command": sanitized, "output": output, "exit_code": exit_code, "duration_ms": duration_ms})
            await self._record_completion(sanitized, exit_code, output, duration_ms)
        except Exception as e:
            await self._broadcast({"type": "command_error", "command": sanitized, "error": str(e)})

    async def _record_completion(self, sanitized: str, exit_code: int, output: str, duration_ms: int) -> None:
        record = {"command": sanitized, "exit_code": exit_code, "output_preview": output[:200], "duration_ms": duration_ms, "timestamp": datetime.now(UTC).isoformat()}
        self._command_history.append(record)
        await self._event_bus.emit(self.session_id, stage="sandbox_command", status="done" if exit_code == 0 else "failed", detail=f"{sanitized[:80]} (exit {exit_code})", source="sandbox", meta={"command": sanitized, "exit_code": exit_code, "duration_ms": duration_ms})
        try:
            await self._workspace_memory.record(workspace_id=self.project_id, project_id=self.project_id, category="sandbox_command", query=sanitized, summary=f"Exit {exit_code} in {duration_ms}ms", status="completed" if exit_code == 0 else "failed", created_by=self.user_id)
        except Exception: pass

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
