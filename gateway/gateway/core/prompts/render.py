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
        # Check if templates already exist
        result = await session.execute(select(PromptTemplate))
        count = len(result.scalars().all())
        if count > 0:
            return

        # Seed some basic templates
        templates = [
            PromptTemplate(
                name="explain-code",
                version="1.0.0",
                system_prompt="You are a helpful assistant that explains code.",
                prompt_template="Explain the following code:\n\n{{code}}",
                variables=["code"],
                owner_org=None,
                visibility="private",
            ),
            PromptTemplate(
                name="summarize-context",
                version="1.0.0",
                system_prompt="You are a helpful assistant that summarizes context.",
                prompt_template="Summarize the following context:\n\n{{context}}",
                variables=["context"],
                owner_org=None,
                visibility="private",
            ),
        ]

        for tpl in templates:
            session.add(tpl)
        await session.commit()
