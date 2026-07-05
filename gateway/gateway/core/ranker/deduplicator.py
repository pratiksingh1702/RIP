"""Deduplicate overlapping source results."""

import hashlib

from .models import ScoredItem


class Deduplicator:
    """Removes duplicate items from the results."""

    def deduplicate(self, items: list[ScoredItem]) -> list[ScoredItem]:
        """Deduplicate items by content hash, keeping highest score."""
        seen = {}
        for item in items:
            content_hash = hashlib.sha256(item.content.encode("utf-8")).hexdigest()
            if content_hash not in seen or item.score > seen[content_hash].score:
                seen[content_hash] = item
        return list(seen.values())
