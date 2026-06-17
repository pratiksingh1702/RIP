"""Search command."""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.table import Table

from core.graph.client import Neo4jClient
from core.projects import resolve_project_id
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.reranker import CrossEncoderReranker
from core.search.searcher import Searcher
from server.config import get_settings

console = Console()


def search(
    query: str,
    limit: int = 20,
    language: str | None = None,
    service: str | None = None,
    entity_type: str | None = None,
    project: str | None = None,
) -> None:
    asyncio.run(
        _search(
            query=query,
            limit=limit,
            language=language,
            service=service,
            entity_type=entity_type,
            project=project,
        )
    )


async def _search(
    query: str,
    limit: int,
    language: str | None,
    service: str | None,
    entity_type: str | None,
    project: str | None,
) -> None:
    settings = get_settings()
    project_id = resolve_project_id(project)
    qdrant_client = QdrantClientWrapper(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        vector_size=embedding_dimension(settings.embedding_model),
    )
    graph_client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    embedder = EmbeddingPipeline(model_name=settings.embedding_model)
    reranker = CrossEncoderReranker()

    try:
        searcher = Searcher(
            qdrant_client=qdrant_client,
            embedder=embedder,
            reranker=reranker,
            graph_client=graph_client,
        )
        filters = {
            "language": language,
            "service": service,
            "entity_type": entity_type,
            "project_id": project_id,
        }
        results = await searcher.hybrid_search(
            query=query,
            filters=filters,
            top_k=limit,
            project_id=project_id,
        )

        if not results:
            console.print("[yellow]No semantic matches found.[/yellow]")
            return

        table = Table(title=f"Hybrid Search Results for: {query}")
        table.add_column("FQN", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("File Path", style="green")
        table.add_column("Score", style="yellow", justify="right")
        table.add_column("Callers/Callees", style="blue")

        for r in results:
            cc = []
            if r.callers:
                cc.append(f"Callers: {', '.join(r.callers)}")
            if r.callees:
                cc.append(f"Callees: {', '.join(r.callees)}")
            cc_str = "\n".join(cc) if cc else "-"

            table.add_row(
                r.entity_id,
                r.entity_type,
                f"{r.file_path}",
                f"{r.score:.4f}",
                cc_str,
            )

        console.print(table)
    finally:
        await qdrant_client.close()
        await graph_client.close()
