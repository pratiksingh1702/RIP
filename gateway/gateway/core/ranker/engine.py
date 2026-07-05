"""Main ranker engine."""

import re
from datetime import datetime

from gateway.core.classifier.models import ClassificationResult, IntentType
from gateway.core.sources.models import SourceResponse

from .compressor import ContextCompressor
from .deduplicator import Deduplicator
from .models import CompressedContext, ScoredItem
from .scorers import AuthorityScorer, PatternScorer, RecencyScorer, SemanticScorer


class RankerEngine:
    """Ranks, deduplicates, and compresses source responses."""

    INTENT_WEIGHTS = {
        IntentType.BUG_FIX: {
            "semantic": 0.25,
            "recency": 0.35,
            "pattern": 0.10,
            "authority": 0.10,
            "centrality": 0.20
        },
        IntentType.FEATURE_ADDITION: {
            "semantic": 0.30,
            "recency": 0.20,
            "pattern": 0.15,
            "authority": 0.10,
            "centrality": 0.25
        },
        IntentType.ARCHITECTURAL_QUESTION: {
            "semantic": 0.35,
            "recency": 0.05,
            "pattern": 0.15,
            "authority": 0.15,
            "centrality": 0.30
        },
        IntentType.REFACTOR: {
            "semantic": 0.25,
            "recency": 0.15,
            "pattern": 0.15,
            "authority": 0.10,
            "centrality": 0.35
        },
        IntentType.INVESTIGATION: {
            "semantic": 0.30,
            "recency": 0.25,
            "pattern": 0.15,
            "authority": 0.10,
            "centrality": 0.20
        },
        IntentType.DOCUMENTATION: {
            "semantic": 0.30,
            "recency": 0.10,
            "pattern": 0.20,
            "authority": 0.10,
            "centrality": 0.30
        }
    }

    def __init__(self):
        self.semantic_scorer = SemanticScorer()
        self.recency_scorer = RecencyScorer()
        self.pattern_scorer = PatternScorer()
        self.authority_scorer = AuthorityScorer()
        self.deduplicator = Deduplicator()
        self.compressor = ContextCompressor()

    async def rank_and_compress(
        self,
        responses: list[SourceResponse],
        classification: ClassificationResult,
        task: str,
        token_budget: int
    ) -> CompressedContext:
        """Rank, deduplicate, and compress source responses."""
        # Convert responses to scored items
        scored_items = []
        for resp in responses:
            if not resp.success or not resp.content:
                continue

            score = await self._calculate_score(resp, classification, task)
            scored_items.append(
                ScoredItem(
                    source=resp.source,
                    query_type=resp.query_type,
                    content=resp.content,
                    metadata=resp.metadata,
                    score=score
                )
            )

        # Deduplicate
        deduplicated = self.deduplicator.deduplicate(scored_items)

        # Compress
        compressed = await self.compressor.compress(deduplicated, token_budget)

        return compressed

    async def _calculate_score(
        self,
        response: SourceResponse,
        classification: ClassificationResult,
        task: str
    ) -> float:
        """Calculate a combined score for an item."""
        weights = self.INTENT_WEIGHTS.get(
            classification.intent,
            self.INTENT_WEIGHTS[IntentType.INVESTIGATION]
        )

        # Pattern score (fast)
        pattern_score = self.pattern_scorer.score(task, response.content)

        # Recency score
        last_modified = response.metadata.get("last_modified")
        if isinstance(last_modified, str):
            try:
                last_modified = datetime.fromisoformat(last_modified)
            except ValueError:
                last_modified = None
        recency_score = self.recency_scorer.score(last_modified, classification.intent)

        # Authority score
        authority_score = self.authority_scorer.score(response.source, response.query_type)

        semantic_score = self._lexical_similarity(task, response.content)
        centrality_score = self._centrality_score(response)

        total_score = (
            weights["semantic"] * semantic_score +
            weights["recency"] * recency_score +
            weights["pattern"] * pattern_score +
            weights["authority"] * authority_score +
            weights["centrality"] * centrality_score
        )

        return total_score

    def _lexical_similarity(self, task: str, content: str) -> float:
        """Cheap semantic proxy based on weighted token overlap."""
        task_terms = self._important_terms(task)
        if not task_terms:
            return 0.0
        content_terms = self._important_terms(content[:8000])
        if not content_terms:
            return 0.0
        overlap = task_terms & content_terms
        return min(1.0, len(overlap) / max(1, len(task_terms)))

    def _important_terms(self, text: str) -> set[str]:
        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "into",
            "what", "where", "when", "does", "how", "add", "fix", "use",
            "need", "code", "file", "class", "function",
        }
        terms = {
            term.lower()
            for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)
        }
        return {term for term in terms if term not in stop_words}

    def _centrality_score(self, response: SourceResponse) -> float:
        """Prefer source responses that describe graph structure or impact."""
        metadata_score = float(response.metadata.get("centrality", 0) or 0)
        if metadata_score:
            return max(0.0, min(1.0, metadata_score))
        query_scores = {
            "architecture": 0.9,
            "impact": 0.85,
            "trace": 0.8,
            "metrics": 0.7,
            "search": 0.55,
        }
        return query_scores.get(response.query_type, 0.45)
