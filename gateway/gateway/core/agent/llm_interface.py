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
        logger.info("AGENT_LLM: provider=%s model=%s", provider, config.model)

        try:
            return await self._call_generic(messages, tools, config)
        except Exception as e:
            logger.error("AGENT_LLM: Call failed: %s", e)
            return LLMResponse(type=ResponseType.TEXT, text=f"Error: {str(e)[:200]}", raw=str(e))

    async def _call_generic(self, messages: list[dict], tools: list[dict], config: LLMConfig) -> LLMResponse:
        import litellm
        provider = (config.provider or "").lower()

        # Build model ID with provider prefix for LiteLLM
        if "/" in config.model:
            model_id = config.model
        elif provider == "groq":
            model_id = f"groq/{config.model}"
        elif provider == "openrouter":
            model_id = f"openrouter/{config.model}"
        elif provider == "ollama":
            model_id = f"ollama/{config.model}"
        else:
            model_id = config.model

        kwargs = {
            "model": model_id,
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.2,
            "timeout": 120,
        }
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.base_url:
            kwargs["api_base"] = config.base_url

        # Try with tools first
        try:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            response = await litellm.acompletion(**kwargs)
            msg = response.choices[0].message
            tokens = response.usage.total_tokens if response.usage else 0

            if msg.tool_calls:
                tc = msg.tool_calls[0]
                try:
                    params = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, AttributeError):
                    params = {}
                return LLMResponse(
                    type=ResponseType.TOOL_CALL,
                    tool_name=tc.function.name,
                    tool_params=params,
                    raw=json.dumps({"tool": tc.function.name, "params": params}),
                    tokens_used=tokens,
                )

            content = msg.content or ""
            return self._parse_json_response(content, tokens)

        except Exception as e:
            err_str = str(e)
            if "tool_use_failed" in err_str or "tool choice is none" in err_str.lower():
                logger.info("AGENT_LLM: Tool call rejected, extracting from error")
                return self._extract_tool_from_error(err_str)
            logger.info("AGENT_LLM: Tools failed, falling back: %s", err_str[:100])
            kwargs.pop("tools", None)
            kwargs.pop("tool_choice", None)
            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content or ""
            return self._parse_json_response(content, response.usage.total_tokens if response.usage else 0)

    def _extract_tool_from_error(self, error_str: str) -> LLMResponse:
        match = re.search(r'"failed_generation"\s*:\s*"(\{[^}]+\})"', error_str)
        if match:
            try:
                data = json.loads(match.group(1).replace('\\"', '"'))
                tool_name = data.get("name", "")
                params = data.get("arguments", {})
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except json.JSONDecodeError:
                        params = {}
                if tool_name:
                    return LLMResponse(
                        type=ResponseType.TOOL_CALL,
                        tool_name=tool_name,
                        tool_params=params,
                        raw=json.dumps({"tool": tool_name, "params": params}),
                        tokens_used=0,
                    )
            except (json.JSONDecodeError, AttributeError):
                pass
        return LLMResponse(type=ResponseType.TEXT, text=f"Error: {error_str[:300]}", raw=error_str)

    def _parse_json_response(self, content: str, tokens: int) -> LLMResponse:
        if not content:
            return LLMResponse(type=ResponseType.TEXT, text="", raw="", tokens_used=tokens)

        strategies = [
            r'\{[^{}]*"tool"\s*:\s*"[^"]+"\s*,[^{}]*\}',
            r'\{[^{}]*"tool"\s*:\s*"[^"]+"[^{}]*\}',
            r'\{[^{}]*"thought"\s*:\s*"[^"]+"[^{}]*\}',
            r'\{[^{}]+\}',
        ]

        for pattern in strategies:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    if "tool" in data:
                        tool_name = str(data.get("tool", ""))
                        params = data.get("params", {})
                        if tool_name == "finish":
                            return LLMResponse(type=ResponseType.FINISH, finish_summary=str(params.get("summary", "")), raw=content, tokens_used=tokens)
                        return LLMResponse(type=ResponseType.TOOL_CALL, tool_name=tool_name, tool_params=params if isinstance(params, dict) else {}, raw=content, tokens_used=tokens)
                    if "thought" in data:
                        return LLMResponse(type=ResponseType.TEXT, text=str(data.get("thought", content)), raw=content, tokens_used=tokens)
                except (json.JSONDecodeError, AttributeError, KeyError):
                    continue

        return LLMResponse(type=ResponseType.TEXT, text=content[:500], raw=content, tokens_used=tokens)
