"""Search indexer."""

from __future__ import annotations

import logging
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
    ) -> None:
        self.qdrant_client = qdrant_client
        self.embedder = embedder

    async def index_entities(self, entities: list[ParsedEntity]) -> int:
        """Embed and upload entities to Qdrant."""
        if not entities:
            logger.info("Embedding generation skipped: 0 entities.")
            return 0
        if self.embedder is None:
            raise RuntimeError("Embedding pipeline is required for entity indexing.")

        embeddings = await self.embedder.embed_entities_async(entities)
        logger.info(
            "Generated embeddings for Qdrant: entities=%s embeddings=%s",
            len(entities),
            len(embeddings),
        )
        points = []
        for entity, embedding in zip(entities, embeddings, strict=False):
            # Qdrant requires uuid or uint. We use uuid5 based on FQN.
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, entity.fqn))
            payload = {
                "entity_id": entity.fqn,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "file_path": entity.file_path,
                "language": entity.language,
                "service": "default",  # Default service
                "owner": "",
                "change_frequency": 0,
                "raw_code": entity.raw_code,
            }
            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        inserted = await self.qdrant_client.upsert(points)
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
            indexed += await self.index_entities(batch)
            if rich_progress and rich_task:
                rich_progress.update(rich_task, advance=len(batch))
            if progress:
                progress.embeddings_generated = indexed
        return indexed

    async def delete_file_embeddings(self, file_path: str) -> int:
        """Delete all embeddings belonging to a specific file."""
        filter_ = Filter(
            must=[FieldCondition(key="file_path", match=MatchValue(value=file_path))]
        )
        deleted = await self.qdrant_client.delete(filter_)
        logger.info(
            "Requested Qdrant delete for file_path=%s deleted_batches=%s",
            file_path,
            deleted,
        )
        return deleted

    async def delete_file_embeddings_many(self, file_paths: list[str]) -> int:
        """Delete embeddings for many files.

        Qdrant supports filter-based deletes; issuing per-file deletes keeps the
        existing payload shape and avoids changing collection semantics.
        """
        deleted = 0
        for file_path in file_paths:
            deleted += await self.delete_file_embeddings(file_path)
        logger.info(
            "Requested Qdrant deletes for %s file paths; completed=%s",
            len(file_paths),
            deleted,
        )
        return deleted
