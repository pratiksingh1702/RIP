"""LLM router and resource pool with database persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import sys

gateway_root = Path(__file__).parent.parent.parent.parent
rip_root = gateway_root.parent
if str(rip_root) not in sys.path:
    sys.path.insert(0, str(rip_root))

from gateway.config import settings
from gateway.storage.database import async_session_factory
from sqlalchemy import text

router_logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    id: str
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    is_custom: bool = False


class LLMRouter:
    def __init__(self):
        self.configs: dict[str, LLMConfig] = {}
        self._loaded = False

    async def _ensure_loaded(self):
        if self._loaded:
            return
        await self._load_from_db()
        if not self.configs:
            await self._seed_from_config_toml()
        self._loaded = True

    async def _load_from_db(self):
        try:
            async with async_session_factory() as session:
                result = await session.execute(text("SELECT id, provider, model, api_key, base_url, is_custom FROM llm_configs"))
                for row in result:
                    self.configs[row[0]] = LLMConfig(id=row[0], provider=row[1], model=row[2], api_key=row[3], base_url=row[4], is_custom=row[5])
            router_logger.info("ROUTER: Loaded %d configs from DB", len(self.configs))
        except Exception as e:
            router_logger.error("ROUTER: Failed to load from DB: %s", e)

    async def _save_to_db(self, config: LLMConfig):
        try:
            async with async_session_factory() as session:
                await session.execute(
                    text("INSERT INTO llm_configs (id, provider, model, api_key, base_url, is_custom, updated_at) VALUES (:id, :provider, :model, :api_key, :base_url, :is_custom, NOW()) ON CONFLICT (id) DO UPDATE SET provider=:provider, model=:model, api_key=:api_key, base_url=:base_url, is_custom=:is_custom, updated_at=NOW()"),
                    {"id": config.id, "provider": config.provider, "model": config.model, "api_key": config.api_key, "base_url": config.base_url, "is_custom": config.is_custom},
                )
                await session.commit()
        except Exception as e:
            router_logger.error("ROUTER: Failed to save to DB: %s", e)

    async def _delete_from_db(self, config_id: str):
        try:
            async with async_session_factory() as session:
                await session.execute(text("DELETE FROM llm_configs WHERE id = :id"), {"id": config_id})
                await session.commit()
        except Exception:
            pass

    async def _seed_from_config_toml(self):
        try: import tomllib
        except ImportError:
            try: import tomli as tomllib
            except ImportError: return
        config_path = Path(".repo-intel/config.toml")
        if not config_path.exists(): return
        try:
            with open(config_path, "rb") as f: data = tomllib.load(f)
            llm = data.get("llm", {})
            p = llm.get("primary_provider", "google")
            m = llm.get("primary_model", "gemini-2.5-flash")
            cfgs = [LLMConfig(id="primary", provider=p, model=m, api_key=llm.get("google_api_key") or None), LLMConfig(id="ollama-local", provider="ollama", model="llama3.1", base_url=llm.get("ollama_host", "http://localhost:11434"))]
            if llm.get("openrouter_api_key"): cfgs.append(LLMConfig(id="openrouter", provider="openrouter", model="openai/gpt-4o", api_key=llm["openrouter_api_key"], base_url=llm.get("openrouter_base_url", "https://openrouter.ai/api/v1")))
            if llm.get("google_api_key"): cfgs.append(LLMConfig(id="google", provider="google", model=m, api_key=llm["google_api_key"]))
            for cfg in cfgs:
                self.configs[cfg.id] = cfg
                await self._save_to_db(cfg)
        except Exception: pass

    async def register_config(self, config: LLMConfig):
        await self._ensure_loaded()
        self.configs[config.id] = config
        await self._save_to_db(config)

    async def remove_config(self, config_id: str) -> bool:
        await self._ensure_loaded()
        if config_id not in self.configs: return False
        del self.configs[config_id]
        await self._delete_from_db(config_id)
        return True

    async def list_configs(self) -> list[dict[str, Any]]:
        await self._ensure_loaded()
        return [{"id": c.id, "provider": c.provider, "model": c.model, "has_api_key": bool(c.api_key), "is_custom": c.is_custom, "base_url": c.base_url} for c in self.configs.values()]

    async def add_custom_config(self, config_id: str, provider: str, model: str, api_key: str | None = None, base_url: str | None = None) -> LLMConfig:
        await self._ensure_loaded()
        cfg = LLMConfig(id=config_id, provider=provider, model=model, api_key=api_key, base_url=base_url, is_custom=True)
        self.configs[config_id] = cfg
        await self._save_to_db(cfg)
        return cfg

    async def update_config(self, config_id: str, provider: str | None = None, model: str | None = None, api_key: str | None = None, base_url: str | None = None) -> LLMConfig | None:
        await self._ensure_loaded()
        if config_id not in self.configs: return None
        cfg = self.configs[config_id]
        if provider is not None: cfg.provider = provider
        if model is not None: cfg.model = model
        if api_key is not None: cfg.api_key = api_key if api_key else None
        if base_url is not None: cfg.base_url = base_url if base_url else None
        await self._save_to_db(cfg)
        return cfg

    async def get_config(self, config_id: str | None = None, provider: str | None = None, model: str | None = None) -> LLMConfig:
        await self._ensure_loaded()
        router_logger.info("ROUTER: get_config called - config_id=%s provider=%s model=%s available=%s", config_id, provider, model, list(self.configs.keys()))
        if provider or model:
            for cfg in self.configs.values():
                if provider and cfg.provider != provider: continue
                if model and cfg.model != model: continue
                router_logger.info("ROUTER: Matched config by provider/model: id=%s", cfg.id)
                return cfg
        if config_id and config_id in self.configs:
            cfg = self.configs[config_id]
            router_logger.info("ROUTER: Found config by id: %s provider=%s model=%s has_key=%s", cfg.id, cfg.provider, cfg.model, bool(cfg.api_key))
            return cfg
        if self.configs:
            cfg = list(self.configs.values())[0]
            router_logger.info("ROUTER: Falling back to first config: %s", cfg.id)
            return cfg
        raise ValueError("No LLM configs available")

    async def get_fallback_chain(self, config_id: str | None = None, provider: str | None = None, model: str | None = None) -> list[LLMConfig]:
        primary = await self.get_config(config_id=config_id, provider=provider, model=model)
        chain = [primary]
        for cfg in self.configs.values():
            if cfg.id != primary.id: chain.append(cfg)
        return chain

    async def query_llm(self, prompt: str, config: LLMConfig, system_prompt: str = "You are an expert software engineer.", max_tokens: int | None = None, temperature: float | None = None) -> str:
        from core.llm.client import query_llm as rip_query_llm
        router_logger.info("ROUTER_LLM: Calling LLM - config_id=%s provider=%s model=%s has_key=%s", config.id, config.provider, config.model, bool(config.api_key))
        errors = []
        chain = await self.get_fallback_chain(config_id=config.id)
        router_logger.info("ROUTER_LLM: Fallback chain: %s", [c.id for c in chain])
        for candidate in chain:
            try:
                router_logger.info("ROUTER_LLM: Trying candidate id=%s provider=%s model=%s", candidate.id, candidate.provider, candidate.model)
                return await rip_query_llm(prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, provider=candidate.provider, model=candidate.model, api_key=candidate.api_key, base_url=candidate.base_url)
            except Exception as exc:
                errors.append(f"{candidate.id}: {exc}")
                router_logger.error("ROUTER_LLM: Candidate failed: %s", exc)
        raise RuntimeError("All LLM configs failed: " + " | ".join(errors))


_llm_router = LLMRouter()
def get_llm_router() -> LLMRouter: return _llm_router
async def seed_llm_configs():
    router = get_llm_router()
    await router._ensure_loaded()
