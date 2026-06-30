"""Git API router for cloning and indexing remote repositories."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from core.git.cloner import get_clone_service

router = APIRouter(prefix="/git", tags=["git"])


class IndexGitRequest(BaseModel):
    git_url: str
    project_name: str
    folder_name: str
    subdirectory: str | None = None
    branch: str = "main"
    keep_clone: bool = True

    @field_validator("folder_name")
    @classmethod
    def validate_folder_name(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("folder_name is required")
        if "/" in candidate or "\\" in candidate or candidate in {".", ".."}:
            raise ValueError("folder_name must be one folder name, not a path")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", candidate):
            raise ValueError("folder_name may only contain letters, numbers, dot, underscore, or dash")
        return candidate

    @field_validator("subdirectory")
    @classmethod
    def validate_subdirectory(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip().replace("\\", "/").strip("/")
        if not candidate:
            return None
        if candidate in {".", ".."} or any(part == ".." for part in candidate.split("/")):
            raise ValueError("subdirectory must stay inside the cloned repository")
        return candidate


class IndexGitResponse(BaseModel):
    job_id: str
    project_name: str
    folder_name: str
    subdirectory: str | None
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    git_url: str
    project_name: str
    folder_name: str
    branch: str
    status: str
    progress_message: str
    project_id: str | None
    clone_path: str | None
    index_path: str | None
    files_indexed: int
    entities_found: int
    error: str | None


@router.post("/index", response_model=IndexGitResponse)
async def start_git_index(request: IndexGitRequest) -> IndexGitResponse:
    """
    Clone a Git repository and index it into RIP.
    Returns immediately with a job_id.
    Poll /git/status/{job_id} to track progress.
    """
    service = get_clone_service()

    job_id = await service.start_clone_and_index(
        git_url=request.git_url,
        project_name=request.project_name,
        folder_name=request.folder_name,
        subdirectory=request.subdirectory,
        branch=request.branch,
        keep_clone=request.keep_clone,
    )

    return IndexGitResponse(
        job_id=job_id,
        project_name=request.project_name,
        folder_name=request.folder_name,
        subdirectory=request.subdirectory,
        status="started",
        message=(
            f"Cloning {request.git_url} into {request.folder_name} and indexing "
            f"{request.subdirectory or 'repository root'}. "
            f"Poll /git/status/{job_id} for progress."
        )
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Get the current status of a Git indexing job.
    Status transitions: pending → cloning → indexing → complete/failed
    """
    service = get_clone_service()
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job.job_id,
        git_url=job.git_url,
        project_name=job.project_name,
        folder_name=job.folder_name,
        branch=job.branch,
        status=job.status.value,
        progress_message=job.progress_message,
        project_id=job.project_id,
        clone_path=job.clone_path,
        index_path=job.index_path,
        files_indexed=job.files_indexed,
        entities_found=job.entities_found,
        error=job.error,
    )


@router.get("/jobs", response_model=list[JobStatusResponse])
async def list_jobs() -> list[JobStatusResponse]:
    """List all Git indexing jobs (active and completed)."""
    service = get_clone_service()
    jobs = service.get_all_jobs()

    return [
        JobStatusResponse(
            job_id=j.job_id,
            git_url=j.git_url,
            project_name=j.project_name,
            folder_name=j.folder_name,
            branch=j.branch,
            status=j.status.value,
            progress_message=j.progress_message,
            project_id=j.project_id,
            clone_path=j.clone_path,
            index_path=j.index_path,
            files_indexed=j.files_indexed,
            entities_found=j.entities_found,
            error=j.error,
        )
        for j in jobs
    ]
