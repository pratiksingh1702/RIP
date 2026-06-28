"""Projects API router for listing and managing indexed repositories."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.projects import delete_project, get_project, list_projects
from core.storage.database import async_session_factory

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectResponse(BaseModel):
    project_id: str
    project_name: str
    indexed_at: str
    files_count: int
    entities_count: int
    languages: list[str]
    git_url: str | None = None
    branch: str | None = None


@router.get("/", response_model=list[ProjectResponse])
async def list_projects_endpoint() -> list[ProjectResponse]:
    """
    List all indexed repositories.
    Used by clients to discover what they can query.
    """
    async with async_session_factory() as session:
        projects = await list_projects(session)
        return [
            ProjectResponse(
                project_id=p.id,
                project_name=p.name,
                indexed_at=p.indexed_at.isoformat() if p.indexed_at else "",
                files_count=p.files_count or 0,
                entities_count=p.entities_count or 0,
                languages=p.languages or [],
                git_url=p.git_url,
                branch=p.branch,
            )
            for p in projects
        ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_endpoint(project_id: str) -> ProjectResponse:
    """Get details of a specific indexed project."""
    async with async_session_factory() as session:
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
            git_url=project.git_url,
            branch=project.branch,
        )


@router.delete("/{project_id}")
async def remove_project_endpoint(project_id: str) -> dict:
    """
    Delete a project and all its indexed data.
    Removes Neo4j nodes, Qdrant vectors, and PostgreSQL metadata.
    """
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        await delete_project(session, project_id)

        return {"message": f"Project {project_id} deleted", "project_name": project.name}
