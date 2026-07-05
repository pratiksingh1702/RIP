"""Context compressor to fit token budget."""


from gateway.core.tokenizer.counter import get_token_counter

from .models import CompressedContext, ScoredItem
from .summarizer import Summarizer


class ContextCompressor:
    """Compresses context to fit within a token budget."""

    def __init__(self):
        self.token_counter = get_token_counter()
        self.summarizer = Summarizer()

    async def compress(
        self,
        items: list[ScoredItem],
        token_budget: int
    ) -> CompressedContext:
        """Compress items to fit token budget, keeping highest scoring."""
        # Sort items by score descending
        sorted_items = sorted(items, key=lambda x: x.score, reverse=True)

        included = []
        excluded = []
        tokens_used = 0

        for item in sorted_items:
            item_tokens = self.token_counter.count(item.content)

            if tokens_used + item_tokens <= token_budget:
                included.append(item)
                tokens_used += item_tokens
            else:
                # Try to summarize the item to fit
                remaining = token_budget - tokens_used
                if remaining > 50:  # Don't summarize if remaining is tiny
                    try:
                        summary = await self.summarizer.summarize(item.content, remaining)
                        summary_tokens = self.token_counter.count(summary)
                        if tokens_used + summary_tokens <= token_budget:
                            included.append(item.model_copy(update={"content": summary}))
                            tokens_used += summary_tokens
                        else:
                            excluded.append(item)
                    except Exception:
                        excluded.append(item)
                else:
                    excluded.append(item)

        total_raw_tokens = sum(self.token_counter.count(i.content) for i in items)
        compression_ratio = tokens_used / max(1, total_raw_tokens)

        return CompressedContext(
            included=included,
            excluded=excluded,
            tokens_used=tokens_used,
            token_budget=token_budget,
            compression_ratio=compression_ratio
        )
