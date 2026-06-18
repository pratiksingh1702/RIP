"""Embedding pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import TYPE_CHECKING

import torch
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from core.parser.base import ParsedEntity

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
QUALITY_MODEL = "BAAI/bge-m3"
MODEL_DIMENSIONS = {
    "all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-m3": 1024,
}


def embedding_dimension(model_name: str) -> int:
    return MODEL_DIMENSIONS.get(model_name, 384)


class EmbeddingPipeline:
    _model_cache: dict[tuple[str, str | None], object] = {}

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device
        self._model: object | None = None
        self._tokenizer: object | None = None
        self._use_onnx: bool = False
        
        # Try to use ONNX for faster inference
        try:
            from optimum.onnxruntime import ORTModelForFeatureExtraction
            from transformers import AutoTokenizer
            
            cache_key = (self.model_name, self.device)
            if cache_key in self._model_cache:
                cached = self._model_cache[cache_key]
                self._model = cached["model"]
                self._tokenizer = cached["tokenizer"]
                self._use_onnx = cached["use_onnx"]
                logger.info("✅ Reusing cached ONNX model")
            else:
                self._model = ORTModelForFeatureExtraction.from_pretrained(
                    model_name, 
                    export=True
                )
                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._use_onnx = True
                self._model_cache[cache_key] = {
                    "model": self._model,
                    "tokenizer": self._tokenizer,
                    "use_onnx": self._use_onnx
                }
                logger.info("✅ Using ONNX Runtime for faster embeddings")
        except ImportError as e:
            logger.info(f"ONNX not available (error: {str(e)}), using standard sentence-transformers")
            self._use_onnx = False

    @property
    def model(self) -> SentenceTransformer | object:
        if self._model is None:
            cache_key = (self.model_name, self.device)
            if cache_key not in self._model_cache:
                self._model_cache[cache_key] = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                )
            self._model = self._model_cache[cache_key]
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self._use_onnx and self._tokenizer:
            # Onnx inference
            inputs = self._tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
            outputs = self._model(**inputs)
            # Mean pooling
            token_embeddings = outputs.last_hidden_state
            attention_mask = inputs["attention_mask"]
            input_mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            embeddings = torch.sum(token_embeddings * input_mask, 1) / torch.clamp(input_mask.sum(1), min=1e-9)
            return embeddings.tolist()
        else:
            # Sentence-transformers fallback
            embeddings = self.model.encode(texts, show_progress_bar=False)
            return [embedding.tolist() for embedding in embeddings]

    async def embed_texts_async(self, texts: list[str]) -> list[list[float]]:
        """Run text embedding in an executor to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.embed_texts, texts)

    def prepare_text(self, entity: ParsedEntity) -> str:
        parts = [
            f"Entity: {entity.name}",
            f"Type: {entity.entity_type}",
            f"Path: {entity.file_path}",
        ]
        if entity.docstring:
            parts.append(f"Docstring: {entity.docstring}")
        parts.append(f"Code:\n{entity.raw_code}")
        return "\n".join(parts)

    def embed_entities(self, entities: list[ParsedEntity]) -> list[list[float]]:
        texts = [self.prepare_text(e) for e in entities]
        return self.embed_texts(texts)

    async def embed_entities_async(self, entities: list[ParsedEntity]) -> list[list[float]]:
        texts = [self.prepare_text(e) for e in entities]
        return await self.embed_texts_async(texts)

    async def embed_entities_with_cache(
        self,
        entities: list[ParsedEntity],
        db_session_factory,
    ) -> list[list[float]]:
        """Embed entities, using cached embeddings where available."""
        cache_hits = 0
        to_embed = []
        cached_results = {}
        entity_hashes = []

        # First, check cache for each entity
        for entity in entities:
            content = entity.raw_code or entity.name
            content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
            entity_hashes.append((entity, content_hash))

        try:
            from core.storage.database import ensure_storage_schema

            await ensure_storage_schema()
            async with db_session_factory() as session:
                from core.storage.models.embedding_cache import EmbeddingCache
                stmt = select(EmbeddingCache).where(
                    EmbeddingCache.content_hash.in_([h for _, h in entity_hashes]),
                    EmbeddingCache.model_name == self.model_name,
                )
                result = await session.execute(stmt)
                for cache_entry in result.scalars():
                    cached_results[cache_entry.content_hash] = json.loads(
                        cache_entry.embedding_json
                    )
                    cache_hits += 1
        except SQLAlchemyError as exc:
            logger.warning("Embedding cache unavailable; embedding without cache: %s", exc)
            return await self.embed_entities_async(entities)

        for entity, content_hash in entity_hashes:
            if content_hash in cached_results:
                continue
            to_embed.append(entity)

        logger.info(
            "Embedding cache: %s hits, %s need embedding",
            cache_hits,
            len(to_embed),
        )

        # Embed only the uncached entities
        new_embeddings = []
        if to_embed:
            new_embeddings = await self.embed_entities_async(to_embed)
            # Store new embeddings in cache
            try:
                async with db_session_factory() as session:
                    from sqlalchemy.dialects.postgresql import insert

                    from core.storage.models.embedding_cache import EmbeddingCache
                    cache_entries = []
                    for entity, embedding in zip(to_embed, new_embeddings, strict=False):
                        content = entity.raw_code or entity.name
                        content_hash = hashlib.sha256(
                            content.encode("utf-8", errors="replace")
                        ).hexdigest()
                        cache_entries.append({
                            "content_hash": content_hash,
                            "fqn": entity.fqn,
                            "embedding_json": json.dumps(embedding),
                            "model_name": self.model_name,
                        })
                    if cache_entries:
                        stmt = insert(EmbeddingCache).values(cache_entries)
                        stmt = stmt.on_conflict_do_nothing(index_elements=["content_hash"])
                        await session.execute(stmt)
                        await session.commit()
            except SQLAlchemyError as exc:
                logger.warning("Embedding cache write skipped: %s", exc)

        # Combine cached and new embeddings
        final_embeddings = []
        new_idx = 0
        for _entity, content_hash in entity_hashes:
            if content_hash in cached_results:
                final_embeddings.append(cached_results[content_hash])
            else:
                final_embeddings.append(new_embeddings[new_idx])
                new_idx += 1

        return final_embeddings
