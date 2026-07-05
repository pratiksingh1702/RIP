"""Prompt ask AI block."""

from __future__ import annotations

from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.llm_pool import get_llm_router
from gateway.core.prompts import PromptRenderer, get_prompt_template


class PromptAskAIBlock(Block):
    id = "prompt.ask_ai"
    kind = BlockKind.PROMPT
    input_schema = {
        "type": "object",
        "properties": {
            "prompt_id": {"type": "string"},
            "variables": {"type": "object"},
            "system_prompt": {"type": "string", "nullable": True},
            "max_tokens": {"type": "integer", "nullable": True},
            "temperature": {"type": "number", "nullable": True},
        },
        "required": ["prompt_id"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "response": {"type": "string"},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "nullable": True},
            "provider": {"type": "string", "nullable": True},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            # Get prompt template
            prompt_id = str(inputs.get("prompt_id") or config.get("prompt_id") or "").strip()
            prompt_tpl = await get_prompt_template(prompt_id)
            if prompt_tpl is None:
                return BlockResult(
                    ok=False,
                    error=f"Prompt template not found: {prompt_id or 'missing prompt_id'}",
                )

            # Render prompt
            renderer = PromptRenderer()
            rendered = renderer.render(prompt_tpl, inputs.get("variables", {}))

            # Call LLM router
            router = get_llm_router()
            llm_config = router.get_config(
                provider=config.get("provider"),
                model=config.get("model"),
            )

            result = await router.query_llm(
                prompt=rendered,
                config=llm_config,
                system_prompt=inputs.get("system_prompt", prompt_tpl.system_prompt or "You are an expert software engineer analyzing a codebase."),
                max_tokens=inputs.get("max_tokens"),
                temperature=inputs.get("temperature"),
            )

            return BlockResult(
                ok=True,
                output={"response": result},
            )
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Ask AI",
            "description": "Calls an LLM using a prompt template",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }


class ApprovalBlock(Block):
    id = "workflow.approval"
    kind = BlockKind.APPROVAL
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string", "nullable": True},
        },
        "required": ["title"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "approved": {"type": "boolean"},
            "approver": {"type": "string", "nullable": True},
            "comment": {"type": "string", "nullable": True},
        },
    }
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        # This block requires manual approval, so it should pause the workflow
        # For now, let's return a pending state with approval request
        return BlockResult(
            ok=False,
            error="Approval required - use answer_missing_input to approve/reject",
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Approval",
            "description": "Requires manual approval before continuing",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }
