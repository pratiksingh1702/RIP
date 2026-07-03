"""OAuth bridge API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from gateway.core import oauth as oauth_manager
from gateway.core.sources.registry import get_source_registry
from gateway.server.schemas.requests import (
    OAuthCallbackRequest,
    OAuthInitiateRequest,
    OAuthReauthorizeRequest,
)

router = APIRouter()


@router.get("/providers")
async def providers():
    """List server-configured OAuth providers without secrets."""
    return {"providers": await oauth_manager.list_providers()}


@router.post("/initiate")
async def initiate(request: OAuthInitiateRequest):
    """Start OAuth and return a provider authorization URL."""
    try:
        result = await oauth_manager.initiate_oauth(
            provider_id=request.provider_id,
            source_name=request.source_name,
            domain_hints=request.domain_hints,
            redirect_uri=request.redirect_uri,
            client_type=request.client_type,
            requested_by=request.requested_by,
        )
        await get_source_registry().refresh()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/callback")
async def callback(request: OAuthCallbackRequest):
    """Complete OAuth by exchanging an authorization code server-side."""
    try:
        result = await oauth_manager.complete_callback(
            state=request.state,
            code=request.code,
            requested_by=request.requested_by,
        )
        await get_source_registry().refresh()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/pending")
async def pending(requested_by: str | None = Query(default=None)):
    """List pending OAuth attempts."""
    return {"pending": await oauth_manager.list_pending(requested_by=requested_by)}


@router.post("/refresh")
async def refresh_due_tokens():
    """Run a manual refresh sweep for due OAuth tokens."""
    await oauth_manager.refresh_due_tokens()
    await get_source_registry().refresh()
    return {"status": "ok"}


@router.post("/sources/{source_id}/reauthorize")
async def reauthorize_source(source_id: str, request: OAuthReauthorizeRequest):
    """Restart OAuth for an existing source."""
    try:
        result = await oauth_manager.reauthorize_source(
            source_id,
            redirect_uri=request.redirect_uri,
            client_type=request.client_type,
            requested_by=request.requested_by,
        )
        await get_source_registry().refresh()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sources/{source_id}/revoke")
async def revoke_source(source_id: str):
    """Disconnect an OAuth source."""
    try:
        result = await oauth_manager.revoke_source(source_id)
        await get_source_registry().refresh()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
