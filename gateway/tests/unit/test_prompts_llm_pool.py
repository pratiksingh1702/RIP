from __future__ import annotations

import sys
import types

import pytest

from gateway.core.llm_pool.router import LLMConfig, LLMRouter
from gateway.core.prompts.render import PromptRenderer


class _Template:
    def __init__(self, prompt_template: str, variables: list[str]) -> None:
        self.prompt_template = prompt_template
        self.variables = variables


def test_prompt_renderer_output_stability():
    renderer = PromptRenderer()
    template = _Template(
        prompt_template="Explain {{symbol}} in {{module}}.",
        variables=["symbol", "module"],
    )

    output = renderer.render(template, {"symbol": "GraphBuilder", "module": "core.graph"})

    assert output == "Explain GraphBuilder in core.graph."


@pytest.mark.asyncio
async def test_llm_router_fallback_chain_on_provider_failure(monkeypatch):
    calls: list[tuple[str | None, str | None]] = []

    fake_client_module = types.ModuleType("core.llm.client")

    async def fake_query_llm(*, prompt, system_prompt, max_tokens, temperature, provider, model):
        calls.append((provider, model))
        if provider == "openai":
            raise RuntimeError("provider unavailable")
        return "fallback-ok"

    fake_client_module.query_llm = fake_query_llm
    monkeypatch.setitem(sys.modules, "core.llm.client", fake_client_module)

    router = LLMRouter()
    router.register_config(LLMConfig(id="primary", provider="openai", model="gpt-4o"))
    router.register_config(LLMConfig(id="fallback", provider="ollama", model="llama3.1"))

    result = await router.query_llm(
        prompt="Explain parser flow",
        config=router.get_config(config_id="primary"),
    )

    assert result == "fallback-ok"
    assert calls == [("openai", "gpt-4o"), ("ollama", "llama3.1")]
