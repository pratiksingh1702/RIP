"""Active project router - persist user's current project on server."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from gateway.server.request_context import gateway_user_id
from gateway.storage.database import async_session_factory

router = APIRouter()


class SetActiveProjectRequest(BaseModel):
    project_id: str | None = None


@router.post("/active")
async def set_active_project(request: Request, body: SetActiveProjectRequest):
    """Set the active project for the current user (by API key)."""
    user_id = gateway_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with async_session_factory() as session:
        if body.project_id is None:
            # Clear active project
            await session.execute(
                text("DELETE FROM user_active_projects WHERE user_id = :uid"),
                {"uid": user_id},
            )
        else:
            # Upsert active project
            await session.execute(
                text("""
                    INSERT INTO user_active_projects (user_id, project_id, updated_at)
                    VALUES (:uid, :pid, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET project_id = :pid, updated_at = NOW()
                """),
                {"uid": user_id, "pid": body.project_id},
            )
        await session.commit()

    return {"ok": True, "user_id": user_id, "project_id": body.project_id}


@router.get("/active")
async def get_active_project(request: Request):
    """Get the active project for the current user."""
    user_id = gateway_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT project_id FROM user_active_projects WHERE user_id = :uid"),
            {"uid": user_id},
        )
        row = result.fetchone()

    if row is None:
        return {"user_id": user_id, "project_id": None}

    return {"user_id": user_id, "project_id": row[0]}


def get_active_project_id(request: Request) -> str | None:
    """Helper: get active project ID for a request (synchronous version for middleware)."""
    import asyncio
    user_id = gateway_user_id(request)
    if not user_id:
        return None
    
    async def _fetch():
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT project_id FROM user_active_projects WHERE user_id = :uid"),
                {"uid": user_id},
            )
            row = result.fetchone()
            return row[0] if row else None
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop for this synchronous call
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _fetch())
                return future.result(timeout=5)
        return asyncio.run(_fetch())
    except Exception:
        return None


async def get_active_project_id_async(request: Request) -> str | None:
    """Helper: get active project ID for a request (async version)."""
    user_id = gateway_user_id(request)
    if not user_id:
        return None
    
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT project_id FROM user_active_projects WHERE user_id = :uid"),
            {"uid": user_id},
        )
        row = result.fetchone()
    return row[0] if row else None
