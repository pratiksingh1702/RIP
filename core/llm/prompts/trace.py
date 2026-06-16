"""Trace explanation prompt template."""

from __future__ import annotations

TRACE_SYSTEM_PROMPT = """You are an expert developer and debugging assistant.
Analyze the following runtime/symbol call path trace. Explain the flow of execution,
highlighting any potential bottlenecks, redundant calls, or vulnerabilities.
"""

TRACE_USER_PROMPT = """Trace Path:
{trace_path}

Provide an explanation of this call path.
"""
