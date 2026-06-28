"""Project metadata and active-project helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage.models.project import Project

ACTIVE_PROJECT_FILE = ".repo-intel/active_project"
DEFAULT_PROJECT_ID = "default"

try:
    # Python 3.11+
    UTC = datetime.UTC
except AttributeError:
    # Older Python versions
    UTC = timezone.utc  # noqa: UP017


def _read_project_config(root: Path) -> dict[str, object]:
    config_path = root.resolve() / ".repo-intel" / "config.toml"
    if not config_path.exists():
        return {}
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return {}
    try:
        with open(config_path, "rb") as handle:
            data = tomllib.load(handle)
    except Exception:
        return {}
    project = data.get("project", {})
    return project if isinstance(project, dict) else {}


@dataclass(frozen=True)
class ProjectRef:
    id: str
    name: str
    root: str | None = None
    language: str = "mixed"
    created_at: datetime | None = None
    git_url: str | None = None
    branch: str | None = None
    files_count: int = 0
    entities_count: int = 0
    languages: list[str] | None = None
    indexed_at: datetime | None = None
    last_reindexed_at: datetime | None = None


def project_id_for_root(root: Path) -> str:
    resolved = str(root.resolve()).lower()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rip-project:{resolved}"))


def project_ref_for_root(root: Path, language: str = "mixed") -> ProjectRef:
    resolved = root.resolve()
    config = _read_project_config(resolved)
    project_id = str(config.get("id") or project_id_for_root(resolved))
    project_name = str(config.get("name") or resolved.name or "repository")
    return ProjectRef(
        id=project_id,
        name=project_name,
        root=str(resolved),
        language=language,
        created_at=datetime.now(UTC),
    )


async def ensure_project(
    session: AsyncSession,
    root: Path,
    language: str = "mixed",
) -> ProjectRef:
    ref = project_ref_for_root(root, language=language)
    existing = await session.get(Project, ref.id)
    if existing is None:
        session.add(
            Project(
                id=ref.id,
                name=ref.name,
                root=ref.root,
                language=ref.language,
                created_at=ref.created_at or datetime.now(UTC),
            )
        )
    else:
        existing.name = ref.name
        existing.root = ref.root
        existing.language = ref.language
    await session.commit()
    return ref


async def upsert_project(
    session: AsyncSession,
    project_id: str,
    project_name: str,
    git_url: str | None = None,
    branch: str | None = None,
    files_count: int = 0,
    entities_count: int = 0,
    languages: list[str] | None = None,
) -> ProjectRef:
    existing = await session.get(Project, project_id)
    now = datetime.now(UTC)
    if existing is None:
        session.add(
            Project(
                id=project_id,
                name=project_name,
                git_url=git_url,
                branch=branch,
                files_count=files_count,
                entities_count=entities_count,
                languages=languages or [],
                created_at=now,
                indexed_at=now,
            )
        )
    else:
        existing.name = project_name
        existing.git_url = git_url
        existing.branch = branch
        existing.files_count = files_count
        existing.entities_count = entities_count
        existing.languages = languages or []
        existing.last_reindexed_at = now
    await session.commit()
    return await get_project(session, project_id)


async def list_projects(session: AsyncSession) -> list[ProjectRef]:
    rows = (await session.execute(select(Project).order_by(Project.created_at))).scalars().all()
    return [
        ProjectRef(
            id=row.id,
            name=row.name,
            root=row.root,
            language=row.language,
            created_at=row.created_at,
            git_url=row.git_url,
            branch=row.branch,
            files_count=row.files_count,
            entities_count=row.entities_count,
            languages=row.languages,
            indexed_at=row.indexed_at,
            last_reindexed_at=row.last_reindexed_at,
        )
        for row in rows
    ]


async def get_project(session: AsyncSession, project_id: str) -> ProjectRef | None:
    row = await session.get(Project, project_id)
    if row is None:
        return None
    return ProjectRef(
        id=row.id,
        name=row.name,
        root=row.root,
        language=row.language,
        created_at=row.created_at,
        git_url=row.git_url,
        branch=row.branch,
        files_count=row.files_count,
        entities_count=row.entities_count,
        languages=row.languages,
        indexed_at=row.indexed_at,
        last_reindexed_at=row.last_reindexed_at,
    )


async def delete_project(session: AsyncSession, project_id: str) -> bool:
    # First delete Neo4j data
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http.exceptions import UnexpectedResponse
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    from core.graph.client import Neo4jClient
    from server.config import get_settings

    settings = get_settings()
    COLLECTION_NAME = "repo_entities"

    # Delete from Neo4j
    neo4j_client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        if await neo4j_client.connect():
            await neo4j_client.execute(
                """
                MATCH (n)
                WHERE n.project_id = $project_id OR (n:Project AND n.id = $project_id)
                DETACH DELETE n
                """,
                {"project_id": project_id},
            )
            await neo4j_client.execute(
                """
                MATCH (n)
                WHERE (n:Developer OR n:Commit) AND NOT (n)--()
                DETACH DELETE n
                """
            )
    finally:
        await neo4j_client.close()

    # Delete from Qdrant
    qdrant_client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    filter_ = Filter(
        must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
    )
    try:
        try:
            await qdrant_client.delete(collection_name=COLLECTION_NAME, points_selector=filter_)
        except UnexpectedResponse:
            pass  # Ignore if collection doesn't exist
    except Exception:
        pass
    finally:
        await qdrant_client.close()

    # Delete from storage
    row = await session.get(Project, project_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


def active_project_path(repo_path: Path | None = None) -> Path:
    base = (repo_path or Path.cwd()).resolve()
    return base / ACTIVE_PROJECT_FILE


def read_active_project(repo_path: Path | None = None) -> str | None:
    path = active_project_path(repo_path)
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def write_active_project(project_id: str, repo_path: Path | None = None) -> Path:
    path = active_project_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(project_id + "\n", encoding="utf-8")
    return path


def resolve_project_id(project: str | None = None, repo_path: Path | None = None) -> str:
    if project:
        return project
    active = read_active_project(repo_path)
    if active:
        return active
    return project_id_for_root(repo_path or Path.cwd())
