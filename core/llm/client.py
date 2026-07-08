"""LiteLLM client with multi-provider fallback support."""

from __future__ import annotations

import logging
import sys
from typing import Any

import litellm

from server.config import get_settings

logger = logging.getLogger(__name__)

# Force debug logging for LLM calls
litellm.set_verbose = True


def _get_provider_config(provider: str, settings: Any) -> dict[str, Any]:
    """Get provider-specific configuration based on provider name."""
    provider = provider.lower()
    logger.info("LLM_CONFIG: Building provider config for: %s", provider)
    if provider == "ollama":
        return {"model_id": f"ollama/{settings.llm_primary_model}", "api_base": settings.ollama_host, "api_key": "ollama"}
    elif provider == "openai":
        return {"model_id": settings.llm_primary_model, "api_base": settings.openai_base_url, "api_key": settings.openai_api_key}
    elif provider == "openrouter":
        return {"model_id": f"openrouter/{settings.llm_primary_model}", "api_base": settings.openrouter_base_url, "api_key": settings.openrouter_api_key}
    elif provider == "anthropic":
        return {"model_id": f"anthropic/{settings.llm_primary_model}", "api_base": None, "api_key": settings.anthropic_api_key}
    elif provider == "google":
        return {"model_id": f"gemini/{settings.llm_primary_model}", "api_base": None, "api_key": settings.google_api_key}
    elif provider == "groq":
        return {"model_id": f"groq/{settings.llm_primary_model}", "api_base": None, "api_key": settings.groq_api_key}
    elif provider == "azure":
        return {"model_id": f"azure/{settings.llm_primary_model}", "api_base": settings.azure_endpoint, "api_key": settings.azure_api_key, "api_version": settings.azure_api_version}
    else:
        return {"model_id": settings.llm_primary_model, "api_base": None, "api_key": None}


async def query_llm(
    prompt: str,
    system_prompt: str = "You are an expert software engineer analyzing a codebase.",
    max_tokens: int | None = None,
    temperature: float | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    """Query the configured LLM using LiteLLM with provider fallback support."""
    settings = get_settings()

    logger.info("LLM_CALL: ========================================")
    logger.info("LLM_CALL: provider=%s model=%s", provider, model)
    logger.info("LLM_CALL: passed_api_key=%s", "YES" if api_key else "NO (will use settings)")
    logger.info("LLM_CALL: passed_base_url=%s", base_url or "None")
    logger.info("LLM_CALL: prompt_length=%d system_prompt_length=%d", len(prompt), len(system_prompt))
    logger.info("LLM_CALL: max_tokens=%s temperature=%s", max_tokens, temperature)

    max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
    temperature = temperature if temperature is not None else settings.llm_temperature

    if provider:
        providers = [provider]
    else:
        providers = [settings.llm_primary_provider] + settings.llm_fallback_providers
    logger.info("LLM_CALL: provider_chain=%s", providers)

    last_error = None

    for provider in providers:
        config = _get_provider_config(provider, settings)
        logger.info("LLM_CALL: Trying provider=%s", provider)

        if model:
            logger.info("LLM_CALL: Using custom model=%s for provider=%s", model, provider)
            if provider == "ollama": model_id = f"ollama/{model}"
            elif provider == "openrouter": model_id = f"openrouter/{model}"
            elif provider == "anthropic": model_id = f"anthropic/{model}"
            elif provider == "google": model_id = f"gemini/{model}"
            elif provider == "groq": model_id = f"groq/{model}"
            elif provider == "azure": model_id = f"azure/{model}"
            else: model_id = model
        else:
            model_id = config["model_id"]

        resolved_api_base = base_url or config.get("api_base")
        resolved_api_key = api_key or config.get("api_key")

        logger.info("LLM_CALL: model_id=%s", model_id)
        logger.info("LLM_CALL: resolved_api_key=%s", "YES" if resolved_api_key else "NO")
        logger.info("LLM_CALL: resolved_api_base=%s", resolved_api_base or "None")

        if provider not in ["ollama"] and not resolved_api_key:
            logger.warning("LLM_CALL: SKIPPING provider=%s - no API key", provider)
            continue

        for attempt in range(settings.llm_retry_count):
            try:
                logger.info("LLM_CALL: Calling litellm.acompletion attempt=%d/%d", attempt + 1, settings.llm_retry_count)

                completion_kwargs = {
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "timeout": settings.llm_timeout,
                }

                if resolved_api_base:
                    completion_kwargs["api_base"] = resolved_api_base
                if resolved_api_key:
                    completion_kwargs["api_key"] = resolved_api_key
                if "api_version" in config:
                    completion_kwargs["api_version"] = config["api_version"]

                logger.info("LLM_CALL: completion_kwargs keys: %s", list(completion_kwargs.keys()))
                logger.info("LLM_CALL: Calling litellm now...")
                sys.stdout.flush()

                response = await litellm.acompletion(**completion_kwargs)

                logger.info("LLM_CALL: GOT RESPONSE from provider=%s", provider)
                result = response.choices[0].message.content or ""
                logger.info("LLM_CALL: response_length=%d", len(result))
                return result

            except Exception as e:
                last_error = e
                logger.error("LLM_CALL: FAILED provider=%s attempt=%d error=%s", provider, attempt + 1, str(e)[:200])
                continue

        logger.error("LLM_CALL: All retries exhausted for provider=%s", provider)

    error_msg = str(last_error) if last_error else "No providers available"
    logger.error("LLM_CALL: ALL PROVIDERS FAILED: %s", error_msg)
    return f"[Fallback Explanation due to LLM error: {error_msg}]\nPrompt Context:\n{prompt}"
