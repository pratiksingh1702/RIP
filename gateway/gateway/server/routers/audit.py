"""Audit log API router."""

from fastapi import APIRouter, HTTPException, Query

from gateway.storage.audit_store import get_audit_store

router = APIRouter()


@router.get("")
@router.get("/")
async def list_audit_logs(
    session_id: str | None = None,
    role: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    """List persisted audit logs."""
    try:
        logs = await get_audit_store().list_logs(
            session_id=session_id,
            role=role,
            limit=limit,
        )
        return {
            "audit_logs": [
                {
                    "id": str(log.id),
                    "timestamp": log.timestamp.isoformat(),
                    "session_id": log.session_id,
                    "user_id": log.user_id,
                    "role": log.role,
                    "action": log.action,
                    "source": log.source,
                    "allowed": log.allowed,
                    "reason": log.reason,
                }
                for log in logs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
