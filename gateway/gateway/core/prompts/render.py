"""Prompt template rendering."""

from __future__ import annotations

from typing import Any
import re
from uuid import UUID

from sqlalchemy import select

from gateway.storage.database import async_session_factory
from gateway.storage.models import PromptTemplate


class PromptRenderer:
    def __init__(self):
        pass

    def render(self, prompt_template: PromptTemplate, context: dict[str, Any]) -> str:
        """Render the template with the given context."""
        result = prompt_template.prompt_template
        for key in context:
            if key in prompt_template.variables:
                result = re.sub(r"\{\{" + re.escape(key) + r"\}\}", str(context[key]), result)
        return result


async def get_prompt_template(prompt_id: str) -> PromptTemplate | None:
    """Get a prompt template by ID or name."""
    normalized = (prompt_id or "").strip()
    if not normalized:
        return None
    async with async_session_factory() as session:
        try:
            template_id = UUID(normalized)
        except ValueError:
            template_id = None
        if template_id is not None:
            template = await session.get(PromptTemplate, template_id)
            if template is not None:
                return template
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.name == normalized)
        )
        return result.scalar_one_or_none()


async def seed_prompt_templates():
    """Seed initial prompt templates."""
    async with async_session_factory() as session:
        result = await session.execute(select(PromptTemplate))
        count = len(result.scalars().all())
        if count > 0:
            return

        templates = [
            PromptTemplate(
                name="explain-code",
                version="1.0.0",
                system_prompt="You are an expert software engineer. Use ONLY the provided context. Cite file paths and line numbers for every claim. If the context is insufficient, say so clearly.",
                prompt_template="Explain the following code in detail:\n\n{{code}}",
                variables=["code"],
                owner_org="system",
                visibility="private",
            ),
            PromptTemplate(
                name="summarize-context",
                version="1.0.0",
                system_prompt="You are an expert software engineer. Use ONLY the provided context below. Be concise and accurate.",
                prompt_template="Summarize the following context from a codebase analysis:\n\n{{context}}",
                variables=["context"],
                owner_org="system",
                visibility="private",
            ),
            PromptTemplate(
                name="context-analysis",
                version="1.0.0",
                system_prompt="You are an expert software engineer analyzing a codebase. Use ONLY the provided context. Never make up information not present in the context. Cite specific files and functions. If you cannot answer from the context, say so.",
                prompt_template="Query: {{query}}\n\nCodebase Context:\n{{context}}\n\nBased on the context above, provide a detailed analysis:\n1. What the relevant code does\n2. Key components and their relationships\n3. How data flows through the system\n4. Any notable patterns or issues",
                variables=["query", "context"],
                owner_org="system",
                visibility="private",
            ),
            PromptTemplate(
                name="root-cause-analysis",
                version="1.0.0",
                system_prompt="You are an expert software debugger. Use ONLY the provided context. Cite exact file paths and line numbers. If you cannot determine the root cause from the context, say so clearly and ask for more information.",
                prompt_template="Bug: {{query}}\n\nCode Context:\n{{code}}\n\nDependencies:\n{{deps}}\n\nRecent Changes:\n{{commits}}\n\nAnalyze the bug and find the root cause. Provide:\n1. Root cause with exact file:line references\n2. Evidence supporting your conclusion\n3. Suggested fix (if possible from context)",
                variables=["query", "code", "deps", "commits"],
                owner_org="system",
                visibility="private",
            ),
        ]

        for tpl in templates:
            session.add(tpl)
        await session.commit()

