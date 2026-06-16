"""LiteLLM client with multi-provider fallback support."""

from __future__ import annotations

import logging
from typing import Any

import litellm

from server.config import get_settings

logger = logging.getLogger(__name__)


def _get_provider_config(provider: str, settings: Any) -> dict[str, Any]:
    """Get provider-specific configuration based on provider name."""
    provider = provider.lower()
    if provider == "ollama":
        return {
            "model_id": f"ollama/{settings.llm_primary_model}",
            "api_base": settings.ollama_host,
            "api_key": "ollama",
        }
    elif provider == "openai":
        return {
            "model_id": settings.llm_primary_model,
            "api_base": settings.openai_base_url,
            "api_key": settings.openai_api_key,
        }
    elif provider == "openrouter":
        return {
            "model_id": f"openrouter/{settings.llm_primary_model}",
            "api_base": settings.openrouter_base_url,
            "api_key": settings.openrouter_api_key,
        }
    elif provider == "anthropic":
        return {
            "model_id": f"anthropic/{settings.llm_primary_model}",
            "api_base": None,
            "api_key": settings.anthropic_api_key,
        }
    elif provider == "google":
        return {
            "model_id": f"gemini/{settings.llm_primary_model}",
            "api_base": None,
            "api_key": settings.google_api_key,
        }
    elif provider == "groq":
        return {
            "model_id": f"groq/{settings.llm_primary_model}",
            "api_base": None,
            "api_key": settings.groq_api_key,
        }
    elif provider == "azure":
        return {
            "model_id": f"azure/{settings.llm_primary_model}",
            "api_base": settings.azure_endpoint,
            "api_key": settings.azure_api_key,
            "api_version": settings.azure_api_version,
        }
    else:
        # Fallback to treating as a generic provider
        return {
            "model_id": settings.llm_primary_model,
            "api_base": None,
            "api_key": None,
        }


async def query_llm(
    prompt: str,
    system_prompt: str = "You are an expert software engineer analyzing a codebase.",
    max_tokens: int | None = None,
    temperature: float | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """Query the configured LLM using LiteLLM with provider fallback support."""
    settings = get_settings()

    # Get config with defaults from settings
    max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
    temperature = temperature if temperature is not None else settings.llm_temperature

    # Build the provider list: if custom provider is given, use only that, else primary + fallbacks
    if provider:
        providers = [provider]
    else:
        providers = [settings.llm_primary_provider] + settings.llm_fallback_providers
    logger.debug("Providers to try: %s", providers)

    last_error = None

    for provider in providers:
        config = _get_provider_config(provider, settings)
        if model:
            # Handle custom model for provider
            if provider == "ollama":
                model_id = f"ollama/{model}"
            elif provider == "openrouter":
                model_id = f"openrouter/{model}"
            elif provider == "anthropic":
                model_id = f"anthropic/{model}"
            elif provider == "google":
                model_id = f"gemini/{model}"
            elif provider == "groq":
                model_id = f"groq/{model}"
            elif provider == "azure":
                model_id = f"azure/{model}"
            else:
                model_id = model
        else:
            model_id = config["model_id"]
        api_base = config["api_base"]
        api_key = config["api_key"]

        # Skip if no API key and provider requires it
        if provider not in ["ollama"] and not api_key:
            logger.debug("Skipping provider %s: no API key available", provider)
            continue

        for attempt in range(settings.llm_retry_count):
            try:
                logger.debug(
                    "Querying LLM with provider=%s model=%s attempt=%d",
                    provider,
                    model_id,
                    attempt + 1,
                )

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

                if api_base:
                    completion_kwargs["api_base"] = api_base
                if api_key:
                    completion_kwargs["api_key"] = api_key
                if "api_version" in config:
                    completion_kwargs["api_version"] = config["api_version"]

                response = await litellm.acompletion(**completion_kwargs)
                result = response.choices[0].message.content or ""
                logger.debug("Successfully got response from provider %s", provider)
                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "LiteLLM query failed for provider=%s model=%s attempt=%d: %s",
                    provider,
                    model_id,
                    attempt + 1,
                    e,
                )
                # Continue to next attempt or provider
                continue

        logger.warning("All retry attempts failed for provider %s", provider)

    # All providers failed, return raw context fallback
    error_msg = str(last_error) if last_error else "No providers available"
    logger.error("All LLM providers failed: %s", error_msg)
    return f"[Fallback Explanation due to LLM error: {error_msg}]\nPrompt Context:\n{prompt}"
