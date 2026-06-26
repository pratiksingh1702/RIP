"""Validate API router."""

from fastapi import APIRouter, HTTPException

from gateway.core.sources.rip_client import RIPSource
from gateway.server.schemas.requests import ValidateChangeRequest
from gateway.server.schemas.responses import ValidateChangeResponse

router = APIRouter()
rip = RIPSource()


@router.post("", response_model=ValidateChangeResponse)
@router.post("/", response_model=ValidateChangeResponse)
async def validate_change(request: ValidateChangeRequest):
    """Validate a code change."""
    try:
        response = await rip.query("impact", {"diff": request.diff, "files": request.files})
        if not response.success:
            raise HTTPException(status_code=500, detail=response.error)
        return ValidateChangeResponse(
            risk_level="medium",
            affected_files=request.files or [],
            impact_summary=response.content[:500],
            warnings=[],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
