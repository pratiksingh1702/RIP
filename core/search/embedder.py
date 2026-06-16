"""Embedding pipeline."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sentence_transformers import SentenceTransformer

if TYPE_CHECKING:
    from core.parser.base import ParsedEntity

DEFAULT_MODEL = "all-MiniLM-L6-v2"
QUALITY_MODEL = "BAAI/bge-m3"
MODEL_DIMENSIONS = {
    DEFAULT_MODEL: 384,
    f"sentence-transformers/{DEFAULT_MODEL}": 384,
    QUALITY_MODEL: 1024,
}


def embedding_dimension(model_name: str) -> int:
    return MODEL_DIMENSIONS.get(model_name, 384)


class EmbeddingPipeline:
    _model_cache: dict[tuple[str, str | None], SentenceTransformer] = {}

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
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
