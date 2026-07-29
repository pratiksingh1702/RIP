"""SignalChannel: Non-blocking asynchronous signal channel between Supervisor and Main Agent."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    MODIFY_PLAN = "modify_plan"
    RETASK_STEP = "retask_step"
    ROLLBACK_STEP = "rollback_step"
    ABORT = "abort"


class AgentSignal(BaseModel):
    signal_id: str
    task_id: str
    signal_type: SignalType
    step_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    issued_by: str = "supervisor"  # user | supervisor | guardrail
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class SignalChannel:
    """Non-blocking signal manager per task_id."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[AgentSignal]] = {}
        self._paused: dict[str, asyncio.Event] = {}
        self._pending_signals: dict[str, list[AgentSignal]] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_queue(self, task_id: str) -> asyncio.Queue[AgentSignal]:
        async with self._lock:
            if task_id not in self._queues:
                self._queues[task_id] = asyncio.Queue()
                event = asyncio.Event()
                event.set()  # Default is NOT paused
                self._paused[task_id] = event
                self._pending_signals[task_id] = []
            return self._queues[task_id]

    async def send_signal(self, signal: AgentSignal) -> None:
        async with self._lock:
            task_id = signal.task_id
            if task_id not in self._queues:
                self._queues[task_id] = asyncio.Queue()
                event = asyncio.Event()
                event.set()
                self._paused[task_id] = event
                self._pending_signals[task_id] = []

            if signal.signal_type == SignalType.PAUSE:
                self._paused[task_id].clear()  # Clear set state -> execution loop will block
            elif signal.signal_type == SignalType.RESUME:
                self._paused[task_id].set()  # Unblock execution loop

            self._pending_signals[task_id].append(signal)
            self._queues[task_id].put_nowait(signal)

    async def poll_signal(self, task_id: str) -> AgentSignal | None:
        """Non-blocking poll for incoming supervisor signals."""
        if task_id not in self._queues:
            return None
        queue = self._queues[task_id]
        if queue.empty():
            return None
        try:
            signal = queue.get_nowait()
            signal.acknowledged = True
            return signal
        except asyncio.QueueEmpty:
            return None

    async def wait_if_paused(self, task_id: str, timeout_seconds: float = 300.0) -> bool:
        """If paused, block until RESUME signal is received or timeout occurs."""
        if task_id not in self._paused:
            return True
        event = self._paused[task_id]
        if event.is_set():
            return True
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            return True
        except asyncio.TimeoutError:
            return False

    async def is_paused(self, task_id: str) -> bool:
        if task_id not in self._paused:
            return False
        return not self._paused[task_id].is_set()


# Global singleton instance
signal_channel = SignalChannel()
