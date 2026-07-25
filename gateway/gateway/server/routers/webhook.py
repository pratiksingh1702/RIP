"""GitHub Webhook — triggers index pre-warming on git push."""
from __future__ import annotations
import asyncio
import logging
from datetime import UTC, datetime
from fastapi import APIRouter, HTTPException, Request
from gateway.core.router.cache import get_route_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])
_debounce_timers: dict[str, asyncio.Task] = {}
_DEBOUNCE_SECONDS = 60

@router.post("/github")
async def github_webhook(request: Request):
    """Receive GitHub push webhook. Debounces and triggers re-index."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    repo_name = body.get("repository", {}).get("full_name", "unknown")
    ref = body.get("ref", "")
    commits = body.get("commits", [])
    logger.info("GitHub webhook: repo=%s, ref=%s, commits=%d", repo_name, ref, len(commits))
    project_id = _extract_project_id(body)
    if project_id:
        _schedule_debounced_reindex(project_id, repo_name)
    return {"status": "ok", "repo": repo_name, "debouncing": True, "debounce_seconds": _DEBOUNCE_SECONDS}

def _extract_project_id(body: dict) -> str | None:
    """Try to match webhook repo to a known project."""
    repo_name = body.get("repository", {}).get("full_name", "")
    if not repo_name:
        return None
    try:
        import asyncio as _asyncio
        from gateway.storage.database import async_session_factory
        from sqlalchemy import text
        async def lookup():
            async with async_session_factory() as session:
                r = await session.execute(text("SELECT id FROM projects WHERE git_url LIKE :url LIMIT 1"), {"url": f"%{repo_name}%"})
                row = r.fetchone()
                return row[0] if row else None
        return _asyncio.get_event_loop().run_until_complete(lookup())
    except Exception:
        return None

def _schedule_debounced_reindex(project_id: str, repo_name: str) -> None:
    """Coalesce multiple pushes into one re-index within DEBOUNCE_SECONDS window."""
    if project_id in _debounce_timers:
        existing = _debounce_timers[project_id]
        if not existing.done():
            existing.cancel()
    async def delayed_reindex():
        await asyncio.sleep(_DEBOUNCE_SECONDS)
        logger.info("Debounce expired — triggering re-index for project=%s", project_id)
        try:
            get_route_cache().invalidate_project(project_id)
        except Exception as e:
            logger.error("Route cache invalidation failed: %s", e)
        try:
            from core.indexer.pipeline import IndexPipeline
            pipeline = IndexPipeline()
            await pipeline.run(project_id=project_id, incremental=True)
            logger.info("Incremental re-index complete for project=%s", project_id)
        except Exception as e:
            logger.error("Re-index failed for project=%s: %s", project_id, e)
    _debounce_timers[project_id] = asyncio.ensure_future(delayed_reindex())
    logger.info("Debounced re-index scheduled for project=%s in %ds", project_id, _DEBOUNCE_SECONDS)
