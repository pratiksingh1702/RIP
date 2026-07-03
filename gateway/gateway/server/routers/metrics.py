"""Metrics API router."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from gateway.core.memory.conflict_detector import ConflictDetector
from gateway.core.memory.store import get_session_store
from gateway.core.sources.registry import get_source_registry
from gateway.server.schemas.responses import MetricsResponse
from gateway.storage.database import async_session_factory
from gateway.storage.models import Session as DbSession

router = APIRouter()


@router.get("", response_model=MetricsResponse)
@router.get("/", response_model=MetricsResponse)
async def get_metrics():
    """Get gateway metrics."""
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(
                    func.count(DbSession.id),
                    func.count(DbSession.id).filter(DbSession.status == "in_progress"),
                    func.coalesce(func.sum(DbSession.tokens_retrieved), 0),
                    func.coalesce(func.sum(DbSession.tokens_delivered), 0),
                )
            )
            sessions, active_sessions, tokens_retrieved, tokens_delivered = result.one()

        registry = get_source_registry()
        await registry.refresh()
        source_health = [
            {
                "name": name,
                "available": source.is_available(),
                "healthy": registry.is_healthy(name),
                "always_on": bool(registry.get_record(name).protected) if registry.get_record(name) else name == "rip",
                "toggleable": not registry.get_record(name).protected if registry.get_record(name) else name != "rip",
                "kind": registry.get_record(name).kind if registry.get_record(name) else "builtin",
            }
            for name, source in registry.sources.items()
        ]

        active_conflicts = 0
        store = get_session_store()
        detector = ConflictDetector()
        active = await store.get_active_sessions()
        for session in active:
            active_conflicts += len(
                await detector.detect(session.id, session.files_accessed)
            )

        return MetricsResponse(
            sessions=sessions,
            active_sessions=active_sessions,
            tokens_retrieved=tokens_retrieved,
            tokens_delivered=tokens_delivered,
            active_conflicts=active_conflicts,
            source_health=source_health,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
