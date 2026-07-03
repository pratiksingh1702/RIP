"""Live pipeline event stream support."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


PipelineEventSink = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class _SessionEvents:
    seq: int
    events: deque[dict[str, Any]]
    subscribers: set[asyncio.Queue[dict[str, Any]]]


class PipelineEventBus:
    """Small in-memory event bus with per-session replay buffers."""

    def __init__(self, max_events_per_session: int = 128):
        self._max_events_per_session = max_events_per_session
        self._sessions: dict[str, _SessionEvents] = defaultdict(
            lambda: _SessionEvents(
                seq=0,
                events=deque(maxlen=max_events_per_session),
                subscribers=set(),
            )
        )
        self._lock = asyncio.Lock()

    async def emit(
        self,
        session_id: str,
        *,
        stage: str,
        status: str,
        detail: str,
        source: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Emit an event and deliver it to active subscribers."""
        async with self._lock:
            session = self._sessions[session_id]
            session.seq += 1
            event = {
                "session_id": session_id,
                "stage": stage,
                "source": source,
                "status": status,
                "detail": detail,
                "meta": meta or {},
                "seq": session.seq,
                "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
            session.events.append(event)
            subscribers = list(session.subscribers)

        for queue in subscribers:
            queue.put_nowait(event)
        return event

    async def replay(self, session_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        """Return buffered events after the caller's last seen sequence."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return []
            return [event for event in session.events if int(event["seq"]) > after_seq]

    async def subscribe(
        self,
        session_id: str,
        *,
        after_seq: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to a session stream, replaying any missed events first."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            session = self._sessions[session_id]
            session.subscribers.add(queue)
            replay_events = [
                event for event in session.events if int(event["seq"]) > after_seq
            ]
        try:
            for event in replay_events:
                yield event
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                session = self._sessions.get(session_id)
                if session is not None:
                    session.subscribers.discard(queue)


_event_bus = PipelineEventBus()


def get_pipeline_event_bus() -> PipelineEventBus:
    """Return the process-local pipeline event bus."""
    return _event_bus
