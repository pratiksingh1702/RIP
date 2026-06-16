"""Cross-encoder reranker."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sentence_transformers import CrossEncoder

if TYPE_CHECKING:
    from core.graph.models import SearchResult


class CrossEncoderReranker:
    _model_cache: dict[tuple[str, str | None], CrossEncoder] = {}

    def __init__(
        self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", device: str | None = None
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            cache_key = (self.model_name, self.device)
            if cache_key not in self._model_cache:
                self._model_cache[cache_key] = CrossEncoder(self.model_name, device=self.device)
            self._model = self._model_cache[cache_key]
        return self._model

    def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 20
    ) -> list[SearchResult]:
        if not results:
            return []

        pairs = []
        for r in results:
            text = (
                f"Entity: {r.name}\n"
                f"Type: {r.entity_type}\n"
                f"Path: {r.file_path}\n"
                f"Code:\n{r.raw_code}"
            )
            pairs.append((query, text))

        scores = self.model.predict(pairs, show_progress_bar=False)
        for r, score in zip(results, scores, strict=False):
            r.score = float(score)

        # Sort by score in descending order
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def rerank_async(
        self, query: str, results: list[SearchResult], top_k: int = 20
    ) -> list[SearchResult]:
        """Run rerank in executor to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.rerank, query, results, top_k)
