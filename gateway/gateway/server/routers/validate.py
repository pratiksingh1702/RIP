"""Validate API router."""

import re

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
        targets = _resolve_impact_targets(request.diff, request.files)
        warnings = []
        summaries = []
        for target in targets:
            response = await rip.query("impact", {"symbol": target})
            if not response.success:
                warnings.append(f"{target}: {response.error}")
                continue
            summaries.append(response.content[:500])
        if not summaries and warnings:
            raise HTTPException(status_code=500, detail="; ".join(warnings))
        affected_files = request.files or _extract_diff_files(request.diff)
        risk_level = "high" if len(affected_files) > 5 else "medium"
        if any("auth" in file.lower() or "payment" in file.lower() for file in affected_files):
            risk_level = "high"
        if not affected_files:
            risk_level = "low"
        return ValidateChangeResponse(
            risk_level=risk_level,
            affected_files=affected_files,
            impact_summary="\n\n".join(summaries) if summaries else "No impact targets resolved.",
            warnings=warnings,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _resolve_impact_targets(diff: str, files: list[str] | None) -> list[str]:
    """Resolve a diff into file/symbol targets that RIP impact can understand."""
    targets = list(files or [])
    targets.extend(_extract_diff_files(diff))
    for match in re.finditer(r"^\+\s*(?:class|def|function)\s+([A-Za-z_][A-Za-z0-9_]*)", diff, re.MULTILINE):
        targets.append(match.group(1))
    deduped = []
    seen = set()
    for target in targets:
        if target and target not in seen:
            seen.add(target)
            deduped.append(target)
    return deduped or ["."]


def _extract_diff_files(diff: str) -> list[str]:
    files = []
    for match in re.finditer(r"^\+\+\+\s+b/(.+)$", diff, re.MULTILINE):
        path = match.group(1).strip()
        if path != "/dev/null":
            files.append(path)
    for match in re.finditer(r"^diff --git a/.+ b/(.+)$", diff, re.MULTILINE):
        files.append(match.group(1).strip())
    return sorted(set(files))
