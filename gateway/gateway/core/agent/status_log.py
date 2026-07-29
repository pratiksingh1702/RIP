"""TaskStatusLog: Thread-safe, append-only structured status log for Supervisor tracking."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from gateway.core.agent.task_state import LogEventType, StatusLogEvent, TaskProgress, StepStatus, FilePlan


class TaskStatusLog:
    """In-memory append-only status log with async event subscribers."""

    def __init__(self) -> None:
        self._events: dict[str, list[StatusLogEvent]] = defaultdict(list)
        self._sequences: dict[str, int] = defaultdict(int)
        self._progress: dict[str, TaskProgress] = {}
        self._subscribers: dict[str, list[asyncio.Queue[StatusLogEvent]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def init_task(self, task_id: str, query: str, total_steps: int = 0, git_branch: str | None = None) -> TaskProgress:
        async with self._lock:
            progress = TaskProgress(
                task_id=task_id,
                original_query=query,
                total_steps=total_steps,
                git_branch=git_branch,
                started_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self._progress[task_id] = progress
            
            event = StatusLogEvent(
                seq=self._next_seq(task_id),
                task_id=task_id,
                event_type=LogEventType.PLAN_CREATED,
                data={"query": query, "total_steps": total_steps, "git_branch": git_branch},
            )
            self._events[task_id].append(event)
            self._notify_subscribers(task_id, event)
            return progress

    async def append_event(
        self,
        task_id: str,
        event_type: LogEventType,
        step_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> StatusLogEvent:
        async with self._lock:
            event = StatusLogEvent(
                seq=self._next_seq(task_id),
                task_id=task_id,
                event_type=event_type,
                step_id=step_id,
                data=data or {},
            )
            self._events[task_id].append(event)
            
            # Update progress metadata
            if task_id in self._progress:
                p = self._progress[task_id]
                p.updated_at = datetime.now(timezone.utc)
                if event_type == LogEventType.STEP_STARTED and step_id:
                    p.current_step_id = step_id
                    for s in p.steps:
                        if s.step_id == step_id:
                            s.status = "running"
                            s.started_at = datetime.now(timezone.utc)
                elif event_type == LogEventType.STEP_COMPLETED and step_id:
                    for idx, s in enumerate(p.steps):
                        if s.step_id == step_id:
                            s.status = "completed"
                            s.completed_at = datetime.now(timezone.utc)
                            p.current_step_index = max(p.current_step_index, idx + 1)
                elif event_type == LogEventType.STEP_FAILED and step_id:
                    for s in p.steps:
                        if s.step_id == step_id:
                            s.status = "failed"
                            s.error = str(data.get("error", "Unknown error"))
                elif event_type == LogEventType.FILE_TOUCHED:
                    file_path = str(data.get("file_path", ""))
                    if file_path and file_path not in p.files_changed:
                        p.files_changed.append(file_path)

            self._notify_subscribers(task_id, event)
            return event

    async def set_steps(self, task_id: str, steps: list[StepStatus]) -> None:
        async with self._lock:
            if task_id in self._progress:
                self._progress[task_id].steps = steps
                self._progress[task_id].total_steps = len(steps)

    async def get_events(self, task_id: str, after_seq: int = 0) -> list[StatusLogEvent]:
        async with self._lock:
            events = self._events.get(task_id, [])
            return [e for e in events if e.seq > after_seq]

    async def get_task_progress(self, task_id: str) -> TaskProgress | None:
        async with self._lock:
            return self._progress.get(task_id)

    def subscribe(self, task_id: str) -> asyncio.Queue[StatusLogEvent]:
        queue: asyncio.Queue[StatusLogEvent] = asyncio.Queue()
        self._subscribers[task_id].append(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue[StatusLogEvent]) -> None:
        if task_id in self._subscribers and queue in self._subscribers[task_id]:
            self._subscribers[task_id].remove(queue)

    def _next_seq(self, task_id: str) -> int:
        self._sequences[task_id] += 1
        return self._sequences[task_id]

    def _notify_subscribers(self, task_id: str, event: StatusLogEvent) -> None:
        for q in self._subscribers.get(task_id, []):
            q.put_nowait(event)


# Global singleton instance
status_log = TaskStatusLog()
