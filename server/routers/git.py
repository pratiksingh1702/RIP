"""Git API router for cloning and indexing remote repositories."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.git.cloner import get_clone_service

router = APIRouter(prefix="/git", tags=["git"])


class IndexGitRequest(BaseModel):
    git_url: str
    project_name: str
    branch: str = "main"
    keep_clone: bool = False


class IndexGitResponse(BaseModel):
    job_id: str
    project_name: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    git_url: str
    project_name: str
    branch: str
    status: str
    progress_message: str
    project_id: str | None
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
        branch=request.branch,
        keep_clone=request.keep_clone,
    )

    return IndexGitResponse(
        job_id=job_id,
        project_name=request.project_name,
        status="started",
        message=(
            f"Cloning {request.git_url} and indexing. "
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
        branch=job.branch,
        status=job.status.value,
        progress_message=job.progress_message,
        project_id=job.project_id,
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
            branch=j.branch,
            status=j.status.value,
            progress_message=j.progress_message,
            project_id=j.project_id,
            files_indexed=j.files_indexed,
            entities_found=j.entities_found,
            error=j.error,
        )
        for j in jobs
    ]
