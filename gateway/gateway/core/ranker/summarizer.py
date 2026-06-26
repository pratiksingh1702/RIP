"""Summarizer for overflow items."""

import structlog

logger = structlog.get_logger(__name__)


class Summarizer:
    """Deterministically compacts content to fit the remaining token budget."""

    async def summarize(self, content: str, max_tokens: int) -> str:
        """Summarize content to max tokens using extractive head/tail compaction."""
        char_limit = max_tokens * 4
        if len(content) <= char_limit:
            return content

        char_budget = max(0, char_limit - 20)
        head_budget = int(char_budget * 0.7)
        tail_budget = char_budget - head_budget
        if tail_budget > 0:
            compacted = (
                content[:head_budget].rstrip()
                + "\n...\n"
                + content[-tail_budget:].lstrip()
            )
        else:
            compacted = content[:char_budget].rstrip()

        logger.debug(
            "Content summarized",
            original_length=len(content),
            summarized_length=len(compacted),
        )
        return compacted
