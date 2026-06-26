"""Semantic similarity scorer."""

import numpy as np


class SemanticScorer:
    """Scores items based on semantic similarity to task."""

    async def score(self, task_embedding: list[float], item_embedding: list[float]) -> float:
        """Calculate cosine similarity between task and item embeddings."""
        if not task_embedding or not item_embedding:
            return 0.0

        dot = np.dot(task_embedding, item_embedding)
        norm_task = np.linalg.norm(task_embedding)
        norm_item = np.linalg.norm(item_embedding)

        if norm_task == 0 or norm_item == 0:
            return 0.0

        return float(dot / (norm_task * norm_item))
