"""Prompt template manager."""
from typing import List, Optional
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select

from gateway.core.prompts.templates import SEED_TEMPLATES
from gateway.storage.database import async_session_factory
from gateway.storage.models import PromptTemplate as DBPromptTemplate


async def seed_prompt_templates() -> None:
    """Seed the database with initial prompt templates."""
    async with async_session_factory() as session:
        existing = await session.execute(select(DBPromptTemplate))
        existing_ids = {row.id for row in existing.scalars()}
        for seed in SEED_TEMPLATES:
            seed_id = _seed_template_uuid(seed.id)
            if seed_id not in existing_ids:
                new_template = DBPromptTemplate(
                    id=seed_id,
                    version="1.0.0",
                    name=seed.name,
                    system_prompt=seed.system_prompt,
                    prompt_template=seed.prompt_template,
                    variables=seed.variables,
                    owner_org="default",
                    visibility=seed.visibility,
                )
                session.add(new_template)
        await session.commit()


async def list_prompt_templates(owner_org: Optional[str] = None) -> List[DBPromptTemplate]:
    """List all prompt templates."""
    async with async_session_factory() as session:
        query = select(DBPromptTemplate)
        if owner_org:
            query = query.where(DBPromptTemplate.owner_org == owner_org)
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_prompt_template(template_id: str) -> Optional[DBPromptTemplate]:
    """Get a prompt template by ID."""
    async with async_session_factory() as session:
        return await session.get(DBPromptTemplate, template_id)


async def create_prompt_template(
    name: str,
    prompt_template: str,
    variables: List[str],
    owner_org: str = "default",
    visibility: str = "private",
    system_prompt: Optional[str] = None,
) -> DBPromptTemplate:
    """Create a new prompt template."""
    new_template = DBPromptTemplate(
        id=uuid4(),
        version="1.0.0",
        name=name,
        system_prompt=system_prompt,
        prompt_template=prompt_template,
        variables=variables,
        owner_org=owner_org,
        visibility=visibility,
    )
    async with async_session_factory() as session:
        session.add(new_template)
        await session.commit()
        await session.refresh(new_template)
        return new_template


def _seed_template_uuid(seed_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"rip.prompt-template.{seed_id}")
