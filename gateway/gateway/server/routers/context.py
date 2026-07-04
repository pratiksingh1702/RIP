"""Context API router."""

from fastapi import APIRouter, HTTPException, Request

from gateway.core.pipeline import GatewayPipeline
from gateway.server.request_context import gateway_user_id
from gateway.server.schemas.requests import GetContextRequest
from gateway.server.schemas.responses import GetContextResponse

router = APIRouter()
pipeline = GatewayPipeline()


@router.post("", response_model=GetContextResponse)
@router.post("/", response_model=GetContextResponse)
async def get_context(request: GetContextRequest, http_request: Request):
    """Get context for a coding task."""
    try:
        context_package = await pipeline.get_context(
            task=request.task,
            max_tokens=request.max_tokens,
            role=request.role,
            trace_session_id=request.session_id,
            project_id=request.project_id,
            user_id=gateway_user_id(http_request),
        )
        return GetContextResponse(
            session_id=context_package.session_id,
            intent=context_package.intent,
            domain=context_package.domain,
            context=context_package.context,
            tokens_used=context_package.tokens_used,
            tokens_retrieved=context_package.tokens_retrieved,
            token_allocation=context_package.token_allocation,
            score_summary=context_package.score_summary,
            conflicts=context_package.conflicts,
            warnings=context_package.warnings,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
