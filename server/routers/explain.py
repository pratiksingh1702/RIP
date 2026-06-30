"""Explain API router."""

from __future__ import annotations

import logging
import re
import time

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm.client import query_llm
from core.llm.context_assembler import ContextAssembler
from core.llm.models import ExplanationRequest
from core.llm.prompts.explain import get_explain_prompt
from core.projects import get_project, resolve_project_id, verify_project_access
from core.search.searcher import Searcher
from core.storage.database import get_db_session
from server.middleware.auth import verify_api_key
from server.schemas.responses import ApiEnvelope

router = APIRouter(tags=["explain"])
logger = logging.getLogger(__name__)


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


def format_analysis_summary(context) -> str:
    lines: list[str] = []
    if getattr(context, "overview", None):
        lines.append(f"Overview: {context.overview}")
    if getattr(context, "feature", None):
        lines.append(f"Feature: {context.feature}")
    if getattr(context, "important_entities", None):
        lines.append(f"Key Entities: {len(context.important_entities)} found")
    if getattr(context, "api_endpoints", None):
        lines.append(f"API Endpoints: {len(context.api_endpoints)} found")
    if getattr(context, "state_flow", None):
        lines.append(f"State Flow: {len(context.state_flow)} steps")

    if not lines:
        return ""
    return "## Analysis Summary\n" + "\n".join(f"- {line}" for line in lines)


def format_workflow_tree(context) -> str:
    workflow_chain = getattr(context, "workflow_chain", []) or []
    if not workflow_chain:
        return ""

    lines = ["## Workflow Tree"]
    for hop in workflow_chain[:15]:
        from_name = hop.get("from") or hop.get("name") or "?"
        to_name = hop.get("to") or ""
        relationship = hop.get("relationship") or "RELATED"
        if to_name:
            lines.append(f"- `{from_name}` -> `{to_name}` ({relationship})")
        else:
            lines.append(f"- `{from_name}`")
    return "\n".join(lines)


def generate_mermaid(context) -> str:
    lines = ["```mermaid", "graph TD"]
    seen: set[str] = set()

    for hop in (getattr(context, "workflow_chain", []) or [])[:20]:
        from_name = str(hop.get("from") or hop.get("name") or "?").replace('"', "'")[:30]
        to_name = str(hop.get("to") or "").replace('"', "'")[:30]
        relationship = str(hop.get("relationship") or "RELATED").replace('"', "'")[:30]
        if to_name:
            edge = f'    {from_name} -->|{relationship}| {to_name}'
            if edge not in seen:
                seen.add(edge)
                lines.append(edge)

    dependency_graph = getattr(context, "dependency_graph", {}) or {}
    for name, deps in list(dependency_graph.items())[:10]:
        name_clean = str(name).replace('"', "'")[:30]
        for dep_name, rel_type in deps[:3]:
            dep_clean = str(dep_name).replace('"', "'")[:30]
            rel_clean = str(rel_type).replace('"', "'")[:30]
            edge = f'    {name_clean} -->|{rel_clean}| {dep_clean}'
            if edge not in seen:
                seen.add(edge)
                lines.append(edge)

    lines.append("```")
    return "\n".join(lines)


def format_dependency_table(context) -> str:
    dependency_graph = getattr(context, "dependency_graph", {}) or {}
    imported_files = getattr(context, "imported_files", []) or []
    if not dependency_graph and not imported_files:
        return ""

    sections: list[str] = []
    if dependency_graph:
        lines = [
            "## Dependency Graph",
            "| Component | Relationship | Target |",
            "|-----------|--------------|--------|",
        ]
        for name, deps in list(dependency_graph.items())[:15]:
            for dep_name, rel_type in deps[:3]:
                lines.append(f"| {name} | {rel_type} | {dep_name} |")
        sections.append("\n".join(lines))

    if imported_files:
        lines = [
            "## Imported Files",
            "| Name | Path | Kind |",
            "|------|------|------|",
        ]
        for item in imported_files:
            target = str(item.get("target") or "")
            name = target.replace("\\", "/").rstrip("/").split("/")[-1] or target
            kind = "external" if item.get("is_external") else "file"
            lines.append(f"| {name} | {target} | {kind} |")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def format_code_snippets(context) -> str:
    snippets: list[dict] = []
    seen: set[tuple] = set()
    for entity in getattr(context, "important_entities", []) or []:
        code = str(entity.get("raw_code") or "").strip()
        if not code:
            continue
        key = (entity.get("name"), entity.get("file_path"), code[:80])
        if key in seen:
            continue
        seen.add(key)
        snippets.append(entity)

    if not snippets:
        return ""

    sections = ["## Relevant Code"]
    for entity in snippets[:5]:
        name = entity.get("name") or "code"
        file_path = entity.get("file_path") or ""
        line_start = entity.get("line_start") or "?"
        line_end = entity.get("line_end") or "?"
        code = str(entity.get("raw_code") or "").strip()[:1600]
        sections.append(
            f"### {name}\n`{file_path}:{line_start}-{line_end}`\n\n```text\n{code}\n```"
        )
    return "\n\n".join(sections)


def format_fallback_context(context) -> str:
    sections: list[str] = []
    workflow_chain = getattr(context, "workflow_chain", []) or []
    if workflow_chain:
        chain_parts: list[str] = []
        seen: set[str] = set()
        for hop in workflow_chain[:10]:
            from_name = hop.get("from") or hop.get("name") or "?"
            to_name = hop.get("to") or ""
            if from_name not in seen:
                chain_parts.append(str(from_name))
                seen.add(from_name)
            if to_name and to_name not in seen:
                chain_parts.append(str(to_name))
                seen.add(to_name)
        if chain_parts:
            sections.append("## Workflow Chain\n" + " -> ".join(chain_parts))

    important_files = getattr(context, "important_files", []) or []
    if important_files:
        sections.append("## Important Files\n" + "\n".join(f"- {item}" for item in important_files[:5]))

    important_entities = getattr(context, "important_entities", []) or []
    if important_entities:
        lines = []
        for entity in important_entities[:5]:
            lines.append(
                f"- {entity.get('name')} ({entity.get('type')}) - {entity.get('file_path')}"
            )
        sections.append("## Key Entities\n" + "\n".join(lines))

    if sections:
        return "\n\n".join(sections)
    return getattr(context, "context_str", "")


def merge_suggestions(context_suggestions: list[str], parsed_suggestions: list[str]) -> list[str]:
    merged: list[str] = []
    for suggestion in [*context_suggestions, *parsed_suggestions]:
        cleaned = suggestion.strip()
        if cleaned and cleaned not in merged:
            merged.append(cleaned)
    return merged[:5]


def compose_explain_response(
    context,
    explanation: str,
    suggestions: list[str],
    *,
    diagram: bool = False,
    tree: bool = False,
    dependencies: bool = False,
    code: bool = False,
) -> str:
    sections: list[str] = []
    if tree:
        sections.append(format_workflow_tree(context))
    if diagram:
        sections.append("## Mermaid Diagram\n" + generate_mermaid(context))
    if dependencies:
        sections.append(format_dependency_table(context))
    if code:
        sections.append(format_code_snippets(context))
    summary = format_analysis_summary(context)
    if summary:
        sections.append(summary)
    sections.append(explanation.strip())
    if suggestions:
        sections.append("## Suggestions\n" + "\n".join(f"- {item}" for item in suggestions))
    return "\n\n".join(section for section in sections if section)


def resolve_explain_project_id(request: ExplanationRequest) -> str:
    if request.project_id:
        return request.project_id
    if request.repo_path:
        return resolve_project_id(repo_path=Path(request.repo_path))
    raise HTTPException(
        status_code=400,
        detail="Either project_id or repo_path is required for explain.",
    )


@router.post("/explain", response_model=ApiEnvelope)
async def explain_endpoint(
    http_request: Request,
    request: ExplanationRequest,
    auth: Annotated[None, Depends(verify_api_key)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> ApiEnvelope:
    start = time.perf_counter()
    resolved_project_id = resolve_explain_project_id(request)
    api_key = getattr(http_request.state, "api_key", None)

    project = await get_project(db, resolved_project_id)
    if project is None or not await verify_project_access(db, api_key, resolved_project_id):
        raise HTTPException(
            status_code=403,
            detail=f"Access to project {resolved_project_id} denied",
        )

    runtime = http_request.app.state.runtime
    assembler = ContextAssembler(runtime.neo4j, project_id=resolved_project_id)
    intent = assembler.detect_intent(request.symbol)
    logger.info(
        "Explain endpoint: detected intent '%s' for query '%s' in project '%s'",
        intent,
        request.symbol,
        resolved_project_id,
    )

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
        project_id=resolved_project_id,
    )
    logger.info("Explain endpoint: hybrid search returned %s results", len(results))

    context = await assembler.assemble_context(
        request.symbol,
        request.context_level,
        search_results=results,
    )
    logger.info("Explain endpoint: assembled graph context for query '%s'", request.symbol)

    if not context.found:
        return ApiEnvelope(
            success=False,
            data=None,
            error=context.context_str,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    if request.no_llm:
        explanation = format_fallback_context(context)
    else:
        system_prompt, user_prompt = get_explain_prompt(
            intent.value,
            request.symbol,
            context.context_str,
        )
        explanation = await query_llm(
            user_prompt,
            system_prompt=system_prompt,
            provider=request.provider,
            model=request.model,
        )
    if explanation.startswith("[Fallback Explanation due to LLM error:"):
        error_msg = explanation.split("LLM error:", 1)[1].split("\n", 1)[0].strip()
        explanation = (
            f"LLM Error: {error_msg}\n\n"
            "Falling back to raw context.\n\n" + context.context_str
        )
    improvements = merge_suggestions(
        getattr(context, "suggestions", []) or [],
        parse_suggested_improvements(explanation),
    )
    composed_explanation = compose_explain_response(
        context,
        explanation,
        improvements,
        diagram=request.diagram,
        tree=request.tree,
        dependencies=request.dependencies,
        code=request.code,
    )

    result = {
        "explanation": composed_explanation,
        "suggested_improvements": improvements,
        "intent": intent.value,
        "project_id": resolved_project_id,
        "project_name": project.name,
        "project_root": project.root,
        "workflow_chain": getattr(context, "workflow_chain", []) or [],
        "dependency_graph": getattr(context, "dependency_graph", {}) or {},
        "imported_files": getattr(context, "imported_files", []) or [],
        "important_files": getattr(context, "important_files", []) or [],
        "important_entities": getattr(context, "important_entities", []) or [],
        "flags": {
            "diagram": request.diagram,
            "tree": request.tree,
            "dependencies": request.dependencies,
            "code": request.code,
            "no_llm": request.no_llm,
            "max_hops": request.max_hops,
        },
        "analysis_summary": {
            "overview": getattr(context, "overview", ""),
            "feature": getattr(context, "feature", None),
            "key_entities": len(getattr(context, "important_entities", []) or []),
            "api_endpoints": len(getattr(context, "api_endpoints", []) or []),
            "state_flow_steps": len(getattr(context, "state_flow", []) or []),
        },
    }

    return ApiEnvelope(
        success=True,
        data=result,
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
