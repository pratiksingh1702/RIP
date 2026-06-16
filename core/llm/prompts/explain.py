"""Explain prompt template."""

from __future__ import annotations

EXPLAIN_SYSTEM_PROMPT = """You are an expert software developer and architect.
Analyze the provided code symbol and its context, and produce:
1. A clear, high-level explanation of its purpose and functionality.
2. A detailed analysis of its repository role, including its callers and callees.
3. A list of 3-5 suggested improvements (refactoring, performance, error handling, or security).

You must output in Markdown format. Keep the explanation concise and highly technical.
"""

EXPLAIN_USER_PROMPT = """Explain the following symbol based on the collected context:

{context}
"""
