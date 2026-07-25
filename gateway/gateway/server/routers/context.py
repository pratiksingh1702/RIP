"""Context API router."""

from fastapi import APIRouter, HTTPException, Request

from gateway.core.pipeline import GatewayPipeline
from gateway.server.request_context import gateway_user_id
from gateway.server.schemas.requests import GetContextRequest
from gateway.server.schemas.responses import GetContextResponse

router = APIRouter()
pipeline = GatewayPipeline()


@router.post("", response_model=GetContextResponse)
@router.post("/stream")
async def get_context_stream(request: GetContextRequest, http_request: Request):
    """Stream context results via SSE as they become available."""
    from fastapi.responses import StreamingResponse
    async def event_stream():
        try:
            context_package = await pipeline.get_context(task=request.task, max_tokens=request.max_tokens, role=request.role, trace_session_id=request.session_id, project_id=request.project_id, user_id=gateway_user_id(http_request))
            import json as _json
            for i, item in enumerate(context_package.context):
                yield f"data: {_json.dumps({'index':i,'total':len(context_package.context),'source':item.source,'content':item.content[:500]})}\n\n"
            yield f"data: {_json.dumps({'type':'complete','session_id':context_package.session_id,'intent':context_package.intent,'tokens_used':context_package.tokens_used})}\n\n"
        except Exception as e:
            yield f"data: {{\"type\":\"error\",\"message\":\"{str(e)}\"}}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
