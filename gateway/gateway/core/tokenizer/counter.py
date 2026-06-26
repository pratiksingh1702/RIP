"""Token counter using tiktoken."""

import tiktoken

from .models import TokenCountResult


class TokenCounter:
    """Counts tokens using tiktoken (GPT-4 encoding)."""

    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_result(self, text: str) -> TokenCountResult:
        """Count tokens and return a result object."""
        return TokenCountResult(
            text=text,
            token_count=self.count(text)
        )


# Global token counter instance
_token_counter: TokenCounter | None = None


def get_token_counter() -> TokenCounter:
    """Get the global token counter."""
    global _token_counter
    if _token_counter is None:
        _token_counter = TokenCounter()
    return _token_counter
