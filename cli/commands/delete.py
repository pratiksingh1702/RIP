"""Delete RIP indexed data."""

from __future__ import annotations

import asyncio

import typer
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import FieldCondition, Filter, MatchValue
from rich.console import Console
from rich.table import Table
from sqlalchemy import delete as sqlalchemy_delete

from core.graph.client import Neo4jClient
from core.storage.database import Base, async_session_factory, engine
from core.storage.models.embedding_cache import EmbeddingCache
from core.storage.models.file_hash import FileHash
from core.storage.models.index_state import IndexState
from core.storage.models.project import Project
from server.config import get_settings

console = Console()
COLLECTION_NAME = "repo_entities"


def delete(
    project: str | None = None,
    yes: bool = False,
    neo4j: bool = True,
    qdrant: bool = True,
    storage: bool = True,
) -> None:
    """Clear RIP data stores."""
    if not any((neo4j, qdrant, storage)):
        console.print("[yellow]Nothing selected to delete.[/yellow]")
        return

    if not yes:
        target = f"project {project}" if project else "ALL RIP data"
        confirmed = typer.confirm(
            f"This will permanently delete {target} from Neo4j, Qdrant, and storage. Continue?"
        )
        if not confirmed:
            console.print("[yellow]Delete cancelled.[/yellow]")
            return

    results = asyncio.run(
        _delete_all(
            project_id=project,
            clear_neo4j=neo4j,
            clear_qdrant=qdrant,
            clear_storage=storage,
        )
    )
    _print_results(results)


async def _delete_all(
    project_id: str | None = None,
    clear_neo4j: bool = True,
    clear_qdrant: bool = True,
    clear_storage: bool = True,
) -> list[tuple[str, str, str]]:
    settings = get_settings()
    results: list[tuple[str, str, str]] = []
    project_snapshot = await _load_project_snapshot(settings, project_id) if project_id else {}

    if clear_neo4j:
        results.append(
            await (
                _clear_project_neo4j(settings, project_id)
                if project_id
                else _clear_neo4j(settings)
            )
        )
    else:
        results.append(("Neo4j", "skipped", "Disabled by option."))

    if clear_qdrant:
        results.append(
            await (
                _clear_project_qdrant(settings, project_id)
                if project_id
                else _clear_qdrant(settings)
            )
        )
    else:
        results.append(("Qdrant", "skipped", "Disabled by option."))

    if clear_storage:
        results.append(
            await (
                _clear_project_storage(project_id, project_snapshot)
                if project_id
                else _clear_storage()
            )
        )
    else:
        results.append(("Storage", "skipped", "Disabled by option."))

    return results


async def _load_project_snapshot(settings, project_id: str | None) -> dict[str, object]:
    if not project_id:
        return {}

    snapshot: dict[str, object] = {"project_id": project_id, "file_paths": [], "fqns": []}
    try:
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if project:
                snapshot["root"] = project.root
    except Exception:
        pass

    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        if await client.connect():
            file_rows = await client.execute(
                "MATCH (f:File {project_id: $project_id}) RETURN f.path AS path",
                {"project_id": project_id},
            )
            entity_rows = await client.execute(
                """
                MATCH (n {project_id: $project_id})
                WHERE n.fqn IS NOT NULL
                RETURN n.fqn AS fqn
                """,
                {"project_id": project_id},
            )
            snapshot["file_paths"] = [row["path"] for row in file_rows if row.get("path")]
            snapshot["fqns"] = [row["fqn"] for row in entity_rows if row.get("fqn")]
    finally:
        await client.close()
    return snapshot


async def _clear_neo4j(settings) -> tuple[str, str, str]:
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        if not await client.connect():
            return ("Neo4j", "skipped", "Unavailable.")
        count_rows = await client.execute("MATCH (n) RETURN count(n) AS count")
        node_count = int(count_rows[0].get("count", 0)) if count_rows else 0
        await client.execute("MATCH (n) DETACH DELETE n")
        return ("Neo4j", "cleared", f"Deleted {node_count} nodes and relationships.")
    finally:
        await client.close()


async def _clear_project_neo4j(settings, project_id: str | None) -> tuple[str, str, str]:
    if not project_id:
        return ("Neo4j", "skipped", "No project id provided.")
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        if not await client.connect():
            return ("Neo4j", "skipped", "Unavailable.")
        count_rows = await client.execute(
            """
            MATCH (n)
            WHERE n.project_id = $project_id OR (n:Project AND n.id = $project_id)
            RETURN count(n) AS count
            """,
            {"project_id": project_id},
        )
        node_count = int(count_rows[0].get("count", 0)) if count_rows else 0
        await client.execute(
            """
            MATCH (n)
            WHERE n.project_id = $project_id OR (n:Project AND n.id = $project_id)
            DETACH DELETE n
            """,
            {"project_id": project_id},
        )
        await client.execute(
            """
            MATCH (n)
            WHERE (n:Developer OR n:Commit) AND NOT (n)--()
            DETACH DELETE n
            """
        )
        return ("Neo4j", "cleared", f"Deleted {node_count} project-scoped nodes.")
    finally:
        await client.close()


async def _clear_qdrant(settings) -> tuple[str, str, str]:
    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    try:
        try:
            collection = await client.get_collection(COLLECTION_NAME)
            points = collection.points_count or 0
            await client.delete_collection(COLLECTION_NAME)
            return ("Qdrant", "cleared", f"Deleted collection {COLLECTION_NAME} ({points} points).")
        except UnexpectedResponse as exc:
            if exc.status_code == 404:
                return ("Qdrant", "cleared", f"Collection {COLLECTION_NAME} did not exist.")
            return ("Qdrant", "error", str(exc))
    except Exception as exc:  # noqa: BLE001 - CLI should report all reset failures cleanly
        return ("Qdrant", "error", str(exc))
    finally:
        await client.close()


async def _clear_project_qdrant(settings, project_id: str | None) -> tuple[str, str, str]:
    if not project_id:
        return ("Qdrant", "skipped", "No project id provided.")
    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    filter_ = Filter(
        must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
    )
    try:
        try:
            matched = await client.count(
                collection_name=COLLECTION_NAME,
                count_filter=filter_,
                exact=True,
            )
            await client.delete(collection_name=COLLECTION_NAME, points_selector=filter_)
            return (
                "Qdrant",
                "cleared",
                f"Deleted {int(matched.count)} points for project {project_id}.",
            )
        except UnexpectedResponse as exc:
            if exc.status_code == 404:
                return ("Qdrant", "cleared", f"Collection {COLLECTION_NAME} did not exist.")
            return ("Qdrant", "error", str(exc))
    except Exception as exc:  # noqa: BLE001 - CLI should report all reset failures cleanly
        return ("Qdrant", "error", str(exc))
    finally:
        await client.close()


async def _clear_storage() -> tuple[str, str, str]:
    try:
        import core.storage.models  # noqa: F401

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        return ("Storage", "cleared", "Dropped and recreated RIP metadata tables.")
    except Exception as exc:  # noqa: BLE001 - CLI should keep reporting partial success
        return ("Storage", "error", str(exc))


async def _clear_project_storage(
    project_id: str | None,
    snapshot: dict[str, object],
) -> tuple[str, str, str]:
    if not project_id:
        return ("Storage", "skipped", "No project id provided.")
    try:
        file_paths = set(str(path) for path in snapshot.get("file_paths", []) if path)
        root = snapshot.get("root")
        if root:
            file_paths.add(str(root))
        root_prefix = (str(root).replace("\\", "/").rstrip("/") + "/") if root else ""
        normalized_paths = {path.replace("\\", "/") for path in file_paths}
        relative_paths = {
            path.removeprefix(root_prefix)
            for path in normalized_paths
            if root_prefix and path.startswith(root_prefix)
        }
        hash_paths = normalized_paths | relative_paths
        fqns = [str(fqn) for fqn in snapshot.get("fqns", []) if fqn]

        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            repo_root = project.root if project else root
            await session.execute(sqlalchemy_delete(Project).where(Project.id == project_id))
            if repo_root:
                await session.execute(
                    sqlalchemy_delete(IndexState).where(IndexState.repo_path == str(repo_root))
                )
            if hash_paths:
                await session.execute(
                    sqlalchemy_delete(FileHash).where(FileHash.path.in_(hash_paths))
                )
            if fqns:
                await session.execute(
                    sqlalchemy_delete(EmbeddingCache).where(EmbeddingCache.fqn.in_(fqns))
                )
            await session.commit()

        details = [f"Deleted project row for {project_id}."]
        if hash_paths:
            details.append(f"Removed file hashes for {len(hash_paths)} known paths.")
        if fqns:
            details.append(f"Removed embedding cache rows for {len(fqns)} known entities.")
        return ("Storage", "cleared", " ".join(details))
    except Exception as exc:  # noqa: BLE001 - CLI should keep reporting partial success
        return ("Storage", "error", str(exc))


def _print_results(results: list[tuple[str, str, str]]) -> None:
    table = Table(title="RIP Data Delete")
    table.add_column("Store")
    table.add_column("Status")
    table.add_column("Details")
    for store, status, details in results:
        style = "green" if status == "cleared" else "yellow" if status == "skipped" else "red"
        table.add_row(store, f"[{style}]{status}[/{style}]", details)
    console.print(table)
