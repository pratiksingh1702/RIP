"""Sessions API router."""

from fastapi import APIRouter, HTTPException
from typing import List

from gateway.core.memory.store import get_session_store
from gateway.core.memory.models import Session

router = APIRouter()
store = get_session_store()


@router.get("", response_model=List[Session])
@router.get("/", response_model=List[Session])
async def list_sessions():
    """List all active sessions."""
    try:
        sessions = await store.get_active_sessions()
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Get details of a specific session."""
    try:
        sessions = await store.get_active_sessions()
        for session in sessions:
            if str(session.id) == session_id:
                return session
        raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
