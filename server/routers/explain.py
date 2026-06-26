"""Explain API router."""

from __future__ import annotations

import logging
import re
import time

from fastapi import APIRouter, Request

from core.llm.client import query_llm
from core.llm.context_assembler import ContextAssembler
from core.llm.models import ExplanationRequest, ExplainIntent
from core.llm.prompts.explain import get_explain_prompt
from core.search.searcher import Searcher
from server.schemas.responses import ApiEnvelope

router = APIRouter(tags=["explain"])
logger = logging.getLogger(__name__)


def detect_intent(query: str) -> ExplainIntent:
    """Simple heuristic intent detection."""
    query_lower = query.lower()
    
    if any(keyword in query_lower for keyword in ["how", "work", "flow", "process", "step"]):
        return ExplainIntent.FLOW
    if any(keyword in query_lower for keyword in ["architecture", "structure", "design", "module"]):
        return ExplainIntent.ARCHITECTURE
    if any(keyword in query_lower for keyword in ["api", "endpoint", "request", "response"]):
        return ExplainIntent.API
    if any(keyword in query_lower for keyword in ["state", "provider", "notifier", "bloc", "cubit"]):
        return ExplainIntent.STATE
    
    return ExplainIntent.SEMANTIC


def parse_suggested_improvements(text: str) -> list[str]:
    improvements = []
    lines = text.splitlines()
    in_improvements_section = False
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if re.search(r"(?i)improvement|refactor|suggestion", line_strip):
            in_improvements_section = True
            continue
        if in_improvements_section:
            match = re.match(r"^[-*+]\s+(.*)$", line_strip) or re.match(
                r"^\d+\.\s+(.*)$",
                line_strip,
            )
            if match:
                improvements.append(match.group(1))

    if not improvements:
        for line in lines:
            line_strip = line.strip()
            match = re.match(r"^[-*+]\s+(.*)$", line_strip) or re.match(
                r"^\d+\.\s+(.*)$",
                line_strip,
            )
            if match:
                improvements.append(match.group(1))

    return improvements[:5]


@router.post("/explain", response_model=ApiEnvelope)
async def explain_endpoint(http_request: Request, request: ExplanationRequest) -> ApiEnvelope:
    start = time.perf_counter()
    runtime = http_request.app.state.runtime
    assembler = ContextAssembler(runtime.neo4j, project_id=request.project_id)
    
    # Step 1: Detect intent
    intent = detect_intent(request.symbol)
    logger.info("Explain endpoint: detected intent '%s' for query '%s'", intent, request.symbol)
    
    # Step 2: First try hybrid search for semantic queries
    logger.info("Explain endpoint: starting hybrid search for query: '%s'", request.symbol)
    searcher = Searcher(
        qdrant_client=runtime.qdrant,
        embedder=runtime.embedder,
        reranker=runtime.reranker,
        graph_client=runtime.neo4j,
    )
    results = await searcher.hybrid_search(
        request.symbol,
        top_k=10,
        project_id=request.project_id,
    )
    logger.info("Explain endpoint: hybrid search returned %s results", len(results))
    
    if results:
        context_data = await assembler.assemble_search_context(request.symbol, results)
        logger.info("Explain endpoint: assembled context from search results")
    else:
        # Fallback to symbol lookup
        logger.info("Explain endpoint: no search results, falling back to symbol lookup")
        context_data = await assembler.assemble_context(request.symbol, request.context_level)
        
    if not context_data.get("found"):
        return ApiEnvelope(
            success=False,
            data=None,
            error=context_data["context_str"],
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    system_prompt, user_prompt = get_explain_prompt(intent, request.symbol, context_data["context_str"])
    explanation = await query_llm(
        user_prompt,
        system_prompt=system_prompt,
        provider=request.provider,
        model=request.model,
    )
    if explanation.startswith("[Fallback Explanation due to LLM error:"):
        error_msg = explanation.split("LLM error:", 1)[1].split("\n", 1)[0].strip()
        explanation = (
            f"⚠️  LLM Error: {error_msg}\n\n"
            "Falling back to raw context.\n\n" + context_data["context_str"]
        )
    improvements = parse_suggested_improvements(explanation)

    result = {
        "explanation": explanation,
        "suggested_improvements": improvements,
        "intent": intent,
    }

    return ApiEnvelope(
        success=True,
        data=result,
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
