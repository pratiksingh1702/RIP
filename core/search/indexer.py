"""Search indexer."""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

if TYPE_CHECKING:
    from core.parser.base import ParsedEntity
    from core.search.client import QdrantClientWrapper
    from core.search.embedder import EmbeddingPipeline

logger = logging.getLogger(__name__)


class SearchIndexer:
    def __init__(
        self,
        qdrant_client: QdrantClientWrapper,
        embedder: EmbeddingPipeline | None,
        db_session_factory=None,
        project_id: str | None = None,
        project_name: str | None = None,
    ) -> None:
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.db_session_factory = db_session_factory
        self.project_id = project_id
        self.project_name = project_name or project_id or ""

    async def index_entities(self, entities: list[ParsedEntity], progress = None) -> int:
        """Embed and upload entities to Qdrant, using cache if available."""
        if not entities:
            logger.info("Embedding generation skipped: 0 entities.")
            return 0
        if self.embedder is None:
            raise RuntimeError("Embedding pipeline is required for entity indexing.")

        embedding_start = time.perf_counter()
        if self.db_session_factory:
            embeddings = await self.embedder.embed_entities_with_cache(
                entities, self.db_session_factory
            )
        else:
            embeddings = await self.embedder.embed_entities_async(entities)
        embedding_time = time.perf_counter() - embedding_start
        logger.info("Index timing: embedding_batch_time=%.2fs", embedding_time)
        if progress:
            progress.embedding_time += embedding_time
        logger.info(
            "Generated embeddings for Qdrant: entities=%s embeddings=%s",
            len(entities),
            len(embeddings),
        )
        points = []
        for entity, embedding in zip(entities, embeddings, strict=False):
            project_id = entity.project_id or self.project_id
            if not project_id:
                raise ValueError(f"project_id is required for Qdrant payload: {entity.fqn}")
            # Qdrant requires uuid or uint. We use uuid5 based on FQN.
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_id}:{entity.fqn}"))
            payload = {
                "project_id": project_id,
                "project_name": self.project_name,
                "entity_id": entity.fqn,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "file_path": entity.file_path,
                "language": entity.language,
                "service": "default",  # Default service
                "owner": "",
                "change_frequency": 0,
                "code_preview": entity.raw_code[:500],
                "line_start": entity.line_start,
                "line_end": entity.line_end,
            }
            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        qdrant_start = time.perf_counter()
        inserted = await self.qdrant_client.upsert(points)
        qdrant_time = time.perf_counter() - qdrant_start
        logger.info("Index timing: qdrant_upsert_batch_time=%.2fs", qdrant_time)
        if progress:
            progress.qdrant_time += qdrant_time
        logger.info("Prepared Qdrant points: %s; inserted: %s", len(points), inserted)
        return inserted

    async def index_entities_batched(
        self,
        entities: list[ParsedEntity],
        batch_size: int = 256,
        progress = None,
        rich_progress = None,
        rich_task = None,
    ) -> int:
        """Embed and upload entities in batches with one model instance per indexer."""
        indexed = 0
        for start in range(0, len(entities), batch_size):
            batch = entities[start : start + batch_size]
            indexed += await self.index_entities(batch, progress=progress)
            if rich_progress and rich_task:
                rich_progress.update(rich_task, advance=len(batch))
            if progress:
                progress.embeddings_generated = indexed
        return indexed

    async def delete_file_embeddings(
        self,
        file_path: str,
        project_id: str | None = None,
    ) -> int:
        """Delete all embeddings belonging to a specific file."""
        project_id = project_id or self.project_id
        if not project_id:
            raise ValueError("project_id is required for Qdrant deletes")
        filter_ = Filter(
            must=[
                FieldCondition(key="file_path", match=MatchValue(value=file_path)),
                FieldCondition(key="project_id", match=MatchValue(value=project_id)),
            ]
        )
        deleted = await self.qdrant_client.delete(filter_)
        logger.info(
            "Requested Qdrant delete for file_path=%s deleted_batches=%s",
            file_path,
            deleted,
        )
        return deleted

    async def delete_file_embeddings_many(
        self,
        file_paths: list[str],
        project_id: str | None = None,
        progress = None,
        rich_progress = None,
        rich_task = None,
    ) -> int:
        """Delete embeddings for many files.

        Qdrant supports filter-based deletes; issuing per-file deletes keeps the
        existing payload shape and avoids changing collection semantics.
        """
        deleted = 0
        project_id = project_id or self.project_id
        for file_path in file_paths:
            deleted += await self.delete_file_embeddings(file_path, project_id=project_id)
            if rich_progress and rich_task:
                rich_progress.update(rich_task, advance=1)
            if progress:
                progress.qdrant_points_deleted = deleted
        logger.info(
            "Requested Qdrant deletes for %s file paths; completed=%s",
            len(file_paths),
            deleted,
        )
        return deleted
