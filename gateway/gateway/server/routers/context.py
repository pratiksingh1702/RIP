"""Context API router."""

import time
from fastapi import APIRouter, HTTPException, Request
import structlog

from gateway.core.pipeline import GatewayPipeline
from gateway.server.request_context import gateway_user_id
from gateway.server.schemas.requests import GetContextRequest
from gateway.server.schemas.responses import GetContextResponse

logger = structlog.get_logger("gateway.api.context")
router = APIRouter()
pipeline = GatewayPipeline()


@router.post("", response_model=GetContextResponse)
@router.post("/stream")
async def get_context_stream(request: GetContextRequest, http_request: Request):
    """Stream context results via SSE as they become available."""
    from fastapi.responses import StreamingResponse
    start_time = time.time()
    user_id = gateway_user_id(http_request)
    logger.info(
        "==================== [API INBOUND STREAM REQUEST] ====================",
        task=request.task,
        effort=request.effort,
        project_id=request.project_id,
        user_id=user_id,
        session_id=request.session_id,
        role=request.role,
        max_tokens=request.max_tokens,
    )
    async def event_stream():
        try:
            context_package = await pipeline.get_context(
                task=request.task,
                max_tokens=request.max_tokens,
                role=request.role,
                effort=request.effort,
                trace_session_id=request.session_id,
                project_id=request.project_id,
                user_id=user_id,
            )
            import json as _json
            for i, item in enumerate(context_package.context):
                yield f"data: {_json.dumps({'index':i,'total':len(context_package.context),'source':item.source,'content':item.content[:500]})}\n\n"
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "==================== [API STREAM RESPONSE COMPLETE] ====================",
                session_id=context_package.session_id,
                intent=context_package.intent,
                tokens_used=context_package.tokens_used,
                context_count=len(context_package.context),
                llm_synthesized=getattr(context_package, 'llm_synthesized', True),
                escalated=getattr(context_package, 'escalated', False),
                route_source=getattr(context_package, 'route_source', None),
                elapsed_ms=elapsed_ms,
            )
            yield f"data: {_json.dumps({'type':'complete','session_id':context_package.session_id,'intent':context_package.intent,'tokens_used':context_package.tokens_used,'llm_synthesized':getattr(context_package,'llm_synthesized',True)})}\n\n"
        except Exception as e:
            logger.error("==================== [API STREAM ERROR] ====================", error=str(e), exc_info=True)
            yield f"data: {{\"type\":\"error\",\"message\":\"{str(e)}\"}}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/", response_model=GetContextResponse)
async def get_context(request: GetContextRequest, http_request: Request):
    """Get context for a coding task."""
    start_time = time.time()
    user_id = gateway_user_id(http_request)
    logger.info(
        "==================== [API INBOUND REQUEST] ====================",
        task=request.task,
        effort=request.effort,
        project_id=request.project_id,
        user_id=user_id,
        session_id=request.session_id,
        role=request.role,
        max_tokens=request.max_tokens,
    )
    try:
        context_package = await pipeline.get_context(
            task=request.task,
            max_tokens=request.max_tokens,
            role=request.role,
            trace_session_id=request.session_id,
            project_id=request.project_id,
            user_id=user_id,
            effort=request.effort,
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "==================== [API RESPONSE SUCCESS] ====================",
            session_id=context_package.session_id,
            intent=context_package.intent,
            domain=context_package.domain,
            tokens_used=context_package.tokens_used,
            tokens_retrieved=context_package.tokens_retrieved,
            context_items=len(context_package.context),
            llm_synthesized=getattr(context_package, 'llm_synthesized', True),
            escalated=getattr(context_package, 'escalated', False),
            route_source=getattr(context_package, 'route_source', None),
            elapsed_ms=elapsed_ms,
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
            llm_synthesized=getattr(context_package, 'llm_synthesized', True),
            escalated=getattr(context_package, 'escalated', False),
            route_source=getattr(context_package, 'route_source', None),
        )
    except Exception as e:
        logger.error(
            "==================== [API REQUEST FAILED] ====================",
            task=request.task,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))
