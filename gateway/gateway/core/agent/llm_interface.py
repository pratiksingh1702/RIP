"""Unified LLM interface supporting native tool calling and JSON-mode fallback."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from gateway.core.llm_pool.router import LLMConfig

logger = logging.getLogger(__name__)


class ResponseType(Enum):
    TOOL_CALL = "tool_call"
    TEXT = "text"
    FINISH = "finish"


@dataclass
class LLMResponse:
    type: ResponseType
    tool_name: str | None = None
    tool_params: dict | None = None
    text: str | None = None
    finish_summary: str | None = None
    raw: str = ""
    tokens_used: int = 0


class LLMInterface:
    async def call_with_tools(self, messages: list[dict], tools: list[dict], config: LLMConfig) -> LLMResponse:
        provider = (config.provider or "").lower()
        logger.info("AGENT_LLM: Calling with provider=%s model=%s has_key=%s", provider, config.model, bool(config.api_key))

        if provider in ("openai", "deepseek"):
            return await self._call_openai_style(messages, tools, config)
        elif provider == "anthropic":
            return await self._call_anthropic_style(messages, tools, config)
        elif provider == "google":
            return await self._call_google_style(messages, tools, config)
        else:
            return await self._call_generic(messages, tools, config)

    async def _call_openai_style(self, messages: list[dict], tools: list[dict], config: LLMConfig) -> LLMResponse:
        import litellm
        try:
            model_id = config.model
            if config.provider == "deepseek":
                model_id = f"deepseek/{config.model}"

            kwargs = {
                "model": model_id,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.2,
                "timeout": 120,
            }
            if config.api_key:
                kwargs["api_key"] = config.api_key
            if config.base_url:
                kwargs["api_base"] = config.base_url

            if tools:
                try:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                    response = await litellm.acompletion(**kwargs)
                    msg = response.choices[0].message
                    if msg.tool_calls:
                        tc = msg.tool_calls[0]
                        try:
                            params = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            params = {}
                        return LLMResponse(
                            type=ResponseType.TOOL_CALL,
                            tool_name=tc.function.name,
                            tool_params=params,
                            raw=json.dumps({"tool": tc.function.name, "params": params}),
                            tokens_used=response.usage.total_tokens if response.usage else 0,
                        )
                except Exception as e:
                    logger.warning("AGENT_LLM: Native tool calling failed, falling back to JSON mode: %s", e)

            kwargs.pop("tools", None)
            kwargs.pop("tool_choice", None)
            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content or ""
            return self._parse_json_response(content, response.usage.total_tokens if response.usage else 0)

        except Exception as e:
            logger.error("AGENT_LLM: OpenAI-style call failed: %s", e)
            return LLMResponse(type=ResponseType.TEXT, text=f"Error: {e}", raw=str(e))

    async def _call_anthropic_style(self, messages: list[dict], tools: list[dict], config: LLMConfig) -> LLMResponse:
        return await self._call_generic(messages, tools, config)

    async def _call_google_style(self, messages: list[dict], tools: list[dict], config: LLMConfig) -> LLMResponse:
        import litellm
        try:
            model_id = f"gemini/{config.model}"
            kwargs = {
                "model": model_id,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.2,
                "timeout": 120,
            }
            if config.api_key:
                kwargs["api_key"] = config.api_key

            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content or ""
            return self._parse_json_response(content, response.usage.total_tokens if response.usage else 0)
        except Exception as e:
            logger.error("AGENT_LLM: Google call failed: %s", e)
            return LLMResponse(type=ResponseType.TEXT, text=f"Error: {e}", raw=str(e))

    async def _call_generic(self, messages: list[dict], tools: list[dict], config: LLMConfig) -> LLMResponse:
        import litellm
        try:
            provider = (config.provider or "").lower()
            if provider == "ollama":
                model_id = f"ollama/{config.model}"
            elif provider == "openrouter":
                model_id = f"openrouter/{config.model}"
            else:
                model_id = config.model

            kwargs = {
                "model": model_id,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.2,
                "timeout": 120,
            }
            if config.api_key:
                kwargs["api_key"] = config.api_key
            if config.base_url:
                kwargs["api_base"] = config.base_url

            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content or ""
            return self._parse_json_response(content, response.usage.total_tokens if response.usage else 0)
        except Exception as e:
            logger.error("AGENT_LLM: Generic call failed: %s", e)
            return LLMResponse(type=ResponseType.TEXT, text=f"Error: {e}", raw=str(e))

    def _parse_json_response(self, content: str, tokens: int) -> LLMResponse:
        json_match = re.search(r'\{[^{}]*"tool"\s*:\s*"[^"]+"\s*,[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                tool_name = data.get("tool", "")
                params = data.get("params", {})
                if tool_name == "finish":
                    return LLMResponse(type=ResponseType.FINISH, finish_summary=params.get("summary", ""), raw=content, tokens_used=tokens)
                return LLMResponse(type=ResponseType.TOOL_CALL, tool_name=tool_name, tool_params=params, raw=content, tokens_used=tokens)
            except json.JSONDecodeError:
                pass

        thought_match = re.search(r'\{[^{}]*"thought"\s*:\s*"[^"]+"[^{}]*\}', content, re.DOTALL)
        if thought_match:
            try:
                data = json.loads(thought_match.group(0))
                return LLMResponse(type=ResponseType.TEXT, text=data.get("thought", content), raw=content, tokens_used=tokens)
            except json.JSONDecodeError:
                pass

        return LLMResponse(type=ResponseType.TEXT, text=content, raw=content, tokens_used=tokens)
