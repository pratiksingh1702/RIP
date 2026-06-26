"""Pattern match scorer."""


class PatternScorer:
    """Scores items based on keyword overlap."""

    def score(self, task: str, item_text: str) -> float:
        """Calculate overlap score between task and item."""
        stop_words = {"the", "a", "an", "is", "in", "to", "for", "of", "with", "and", "or", "but"}

        task_words = set(task.lower().split()) - stop_words
        item_words = set(item_text.lower().split()) - stop_words

        if not task_words:
            return 0.0

        overlap = len(task_words & item_words)
        return min(1.0, (overlap / len(task_words)) * 2)
