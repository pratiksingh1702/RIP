#!/usr/bin/env python3
import asyncio
from gateway.core.prompts.manager import seed_prompt_templates
from gateway.core.workflow.engine import seed_workflows

async def main():
    await seed_prompt_templates()
    await seed_workflows()
    print("Seeding completed!")

if __name__ == "__main__":
    asyncio.run(main())
