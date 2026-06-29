"""Projects API router for listing and managing indexed repositories."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.projects import api_key_access_scope, delete_project, get_project, list_projects
from core.storage.database import async_session_factory
from core.storage.models import ApiKey
from server.middleware.auth import verify_api_key

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectResponse(BaseModel):
    project_id: str
    project_name: str
    indexed_at: str
    files_count: int
    entities_count: int
    languages: list[str]
    root: str | None = None
    git_url: str | None = None
    branch: str | None = None


@router.get("/", response_model=list[ProjectResponse])
async def list_projects_endpoint(
    request: Request,
    auth: Annotated[None, Depends(verify_api_key)] = None,
) -> list[ProjectResponse]:
    """
    List all indexed repositories.
    Used by clients to discover what they can query.

    Isolation:
    - If key is tied to a project, only that project + public projects are shown.
    - Public projects are those not tied to any active API key.
    """
    api_key: ApiKey | None = getattr(request.state, "api_key", None)
    associated_project_id = api_key.project_id if api_key else None
    is_global = api_key_access_scope(api_key) == "all"

    async with async_session_factory() as session:
        projects = await list_projects(
            session,
            associated_project_id=associated_project_id,
            is_global=is_global,
        )
        return [
            ProjectResponse(
                project_id=p.id,
                project_name=p.name,
                indexed_at=p.indexed_at.isoformat() if p.indexed_at else "",
                files_count=p.files_count or 0,
                entities_count=p.entities_count or 0,
                languages=p.languages or [],
                root=p.root,
                git_url=p.git_url,
                branch=p.branch,
            )
            for p in projects
        ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_endpoint(
    project_id: str,
    request: Request,
    auth: Annotated[None, Depends(verify_api_key)] = None,
) -> ProjectResponse:
    """Get details of a specific indexed project."""
    api_key: ApiKey | None = getattr(request.state, "api_key", None)
    async with async_session_factory() as session:
        from core.projects import verify_project_access
        if not await verify_project_access(session, api_key, project_id):
            raise HTTPException(status_code=403, detail=f"Access to project {project_id} denied")

        project = await get_project(session, project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        return ProjectResponse(
            project_id=project.id,
            project_name=project.name,
            indexed_at=project.indexed_at.isoformat() if project.indexed_at else "",
            files_count=project.files_count or 0,
            entities_count=project.entities_count or 0,
            languages=project.languages or [],
            root=project.root,
            git_url=project.git_url,
            branch=project.branch,
        )


@router.delete("/{project_id}")
async def remove_project_endpoint(
    project_id: str,
    request: Request,
    auth: Annotated[None, Depends(verify_api_key)] = None,
) -> dict:
    """
    Delete a project and all its indexed data.
    Removes Neo4j nodes, Qdrant vectors, and PostgreSQL metadata.
    """
    api_key: ApiKey | None = getattr(request.state, "api_key", None)
    async with async_session_factory() as session:
        from core.projects import verify_project_access
        if not await verify_project_access(session, api_key, project_id):
            raise HTTPException(status_code=403, detail=f"Access to project {project_id} denied")

        project = await get_project(session, project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        await delete_project(session, project_id)

        return {"message": f"Project {project_id} deleted", "project_name": project.name}
