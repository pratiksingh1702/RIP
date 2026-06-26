"""Summarizer for overflow items (Phase 6)."""

import structlog

logger = structlog.get_logger(__name__)


class Summarizer:
    """Summarizes content to fit token budget."""

    async def summarize(self, content: str, max_tokens: int) -> str:
        """Summarize content to max tokens (simple truncation for now)."""
        # Simple implementation: truncate and add "..."
        # TODO: Replace with actual LLM-based summarization later
        if len(content) <= max_tokens * 4:  # Rough estimate: 1 token ≈ 4 chars
            return content

        truncated = content[:max_tokens * 4 - 3] + "..."
        logger.debug(
            "Content summarized",
            original_length=len(content),
            summarized_length=len(truncated)
        )
        return truncated
