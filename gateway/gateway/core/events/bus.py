"""Postgres-backed event bus for cross-cutting concerns."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID as UUIDType
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from gateway.storage.database import async_session_factory
from gateway.storage.models import EventStore as DBEventStore


@dataclass
class Event:
    id: UUIDType
    org_id: str | None
    project_id: str | None
    session_id: str | None
    workflow_run_id: str | None
    event_type: str
    source_block_id: str | None
    payload: dict[str, Any]
    ts: datetime


class EventBus:
    """Event bus with publish/subscribe, backed by Postgres."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable[[Event], Awaitable[None]]]] = {}
        self._lock = asyncio.Lock()

    async def publish(
        self,
        event_type: str,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        workflow_run_id: str | None = None,
        source_block_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Event:
        """Publish an event to the bus."""
        event = Event(
            id=uuid4(),
            org_id=org_id,
            project_id=project_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            event_type=event_type,
            source_block_id=source_block_id,
            payload=payload or {},
            ts=datetime.now(UTC),
        )

        # Store in Postgres
        async with async_session_factory() as session:
            db_event = DBEventStore(
                id=event.id,
                org_id=event.org_id,
                project_id=event.project_id,
                session_id=event.session_id,
                workflow_run_id=event.workflow_run_id,
                event_type=event.event_type,
                source_block_id=event.source_block_id,
                payload=event.payload,
                ts=event.ts,
            )
            session.add(db_event)
            await session.commit()

        # Notify subscribers
        async with self._lock:
            for subscriber in self._subscribers.get(event_type, []):
                asyncio.create_task(subscriber(event))
            for subscriber in self._subscribers.get("*", []):
                asyncio.create_task(subscriber(event))

        return event

    async def subscribe(
        self,
        event_types: str | list[str] = "*",
    ) -> AsyncIterator[Event]:
        """Subscribe to events."""
        queue: asyncio.Queue[Event] = asyncio.Queue()

        async def handler(event: Event):
            queue.put_nowait(event)

        async with self._lock:
            types = event_types if isinstance(event_types, list) else [event_types]
            for typ in types:
                if typ not in self._subscribers:
                    self._subscribers[typ] = []
                self._subscribers[typ].append(handler)

        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                for typ in types:
                    if typ in self._subscribers:
                        self._subscribers[typ].remove(handler)
                        if not self._subscribers[typ]:
                            del self._subscribers[typ]


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Return the global event bus instance."""
    return _event_bus
