"""LLM router and resource pool."""

from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path

# Add RIP root to path so we can import RIP's core modules
gateway_root = Path(__file__).parent.parent.parent.parent  # gateway/
rip_root = gateway_root.parent  # RIP/
if str(rip_root) not in sys.path:
    sys.path.insert(0, str(rip_root))

from gateway.config import settings


@dataclass
class LLMConfig:
    id: str
    provider: str
    model: str
    api_key: str | None = None


class LLMRouter:
    def __init__(self):
        self.configs: dict[str, LLMConfig] = {}

    def register_config(self, config: LLMConfig):
        self.configs[config.id] = config

    def get_config(self, config_id: str | None = None, provider: str | None = None, model: str | None = None) -> LLMConfig:
        # If provider/model specified, try to find a matching config
        if provider or model:
            for cfg in self.configs.values():
                if provider and cfg.provider != provider:
                    continue
                if model and cfg.model != model:
                    continue
                return cfg
        # Fallback to config_id or first config
        if config_id and config_id in self.configs:
            return self.configs[config_id]
        if self.configs:
            return list(self.configs.values())[0]
        raise ValueError("No LLM configs available")

    def get_fallback_chain(
        self,
        config_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> list[LLMConfig]:
        """Return ordered configs to try for a request.

        Priority:
        1. Explicit provider/model or config_id match
        2. Remaining registered configs in insertion order
        """
        if not self.configs:
            raise ValueError("No LLM configs available")

        chain: list[LLMConfig] = []
        preferred = self.get_config(config_id=config_id, provider=provider, model=model)
        chain.append(preferred)
        for cfg in self.configs.values():
            if cfg.id != preferred.id:
                chain.append(cfg)
        return chain

    async def query_llm(
        self,
        prompt: str,
        config: LLMConfig,
        system_prompt: str = "You are an expert software engineer analyzing a codebase.",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Query the LLM using RIP's existing query_llm function."""
        from core.llm.client import query_llm as rip_query_llm

        errors: list[str] = []
        chain = self.get_fallback_chain(config_id=config.id)
        for candidate in chain:
            try:
                return await rip_query_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    provider=candidate.provider,
                    model=candidate.model,
                )
            except Exception as exc:
                errors.append(f"{candidate.id}: {exc}")

        raise RuntimeError("All LLM configs failed: " + " | ".join(errors))


def seed_llm_configs():
    """Seed initial LLM configs from settings."""
    router = get_llm_router()
    # Add configs based on available settings
    if hasattr(settings, "openai_api_key") and settings.openai_api_key:
        router.register_config(
            LLMConfig(
                id="openai-gpt-4",
                provider="openai",
                model="gpt-4",
                api_key=settings.openai_api_key,
            )
        )
    if hasattr(settings, "anthropic_api_key") and settings.anthropic_api_key:
        router.register_config(
            LLMConfig(
                id="anthropic-claude",
                provider="anthropic",
                model="claude-3-5-sonnet",
                api_key=settings.anthropic_api_key,
            )
        )
    # Add default config for testing
    router.register_config(
        LLMConfig(
            id="default",
            provider="ollama",
            model="llama3.1",
        )
    )


_llm_router = LLMRouter()


def get_llm_router() -> LLMRouter:
    return _llm_router
