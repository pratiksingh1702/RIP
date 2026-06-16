"""Explain API router."""

from __future__ import annotations

import re
import time

from fastapi import APIRouter, Request

from core.llm.client import query_llm
from core.llm.context_assembler import ContextAssembler
from core.llm.models import ExplanationRequest
from core.llm.prompts.explain import EXPLAIN_SYSTEM_PROMPT, EXPLAIN_USER_PROMPT
from core.search.searcher import Searcher
from server.schemas.responses import ApiEnvelope

router = APIRouter(tags=["explain"])


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
    assembler = ContextAssembler(runtime.neo4j)
    context_data = await assembler.assemble_context(request.symbol, request.context_level)
    if not context_data.get("found"):
        searcher = Searcher(
            qdrant_client=runtime.qdrant,
            embedder=runtime.embedder,
            reranker=runtime.reranker,
            graph_client=runtime.neo4j,
        )
        results = await searcher.hybrid_search(request.symbol, top_k=10)
        context_data = await assembler.assemble_search_context(request.symbol, results)
    if not context_data.get("found"):
        return ApiEnvelope(
            success=False,
            data=None,
            error=context_data["context_str"],
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    prompt = EXPLAIN_USER_PROMPT.format(context=context_data["context_str"])
    explanation = await query_llm(
        prompt,
        system_prompt=EXPLAIN_SYSTEM_PROMPT,
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
    }

    return ApiEnvelope(
        success=True,
        data=result,
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
