"""HTTP request blocks for calling external APIs."""

from __future__ import annotations

import json as json_mod
from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext


class HTTPGetBlock(Block):
    id = "http.get"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "headers": {"type": "object", "description": "Request headers"},
            "params": {"type": "object", "description": "Query parameters"},
            "timeout_seconds": {"type": "integer", "default": 30},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "status_code": {"type": "integer"},
            "body": {"type": "string"},
            "headers": {"type": "object"},
            "duration_ms": {"type": "integer"},
        },
    }
    config_schema = {"type": "object", "properties": {"base_url": {"type": "string"}, "default_headers": {"type": "object"}}}
    requires_capabilities = ["NETWORK"]

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        import time
        try:
            import httpx
        except ImportError:
            return BlockResult(ok=False, error="httpx not installed. Run: pip install httpx")

        try:
            url = str(inputs["url"])
            base_url = config.get("base_url", "")
            if base_url and not url.startswith("http"):
                url = base_url.rstrip("/") + "/" + url.lstrip("/")

            headers = {**config.get("default_headers", {}), **inputs.get("headers", {})}
            params = inputs.get("params", {})
            timeout = int(inputs.get("timeout_seconds", 30))

            start = time.monotonic()
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, headers=headers, params=params)
            duration_ms = int((time.monotonic() - start) * 1000)

            return BlockResult(ok=resp.is_success, output={
                "status_code": resp.status_code,
                "body": resp.text[:100000],
                "headers": dict(resp.headers),
                "duration_ms": duration_ms,
            })
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "HTTP GET", "description": "Make a GET request", "category": "HTTP", "display_icon": "🌐", "display_color": "#0EA5E9", "input_schema": self.input_schema, "output_schema": self.output_schema}


class HTTPPostBlock(Block):
    id = "http.post"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "headers": {"type": "object"},
            "body": {"type": "object", "description": "JSON body"},
            "timeout_seconds": {"type": "integer", "default": 30},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "status_code": {"type": "integer"},
            "body": {"type": "string"},
            "headers": {"type": "object"},
            "duration_ms": {"type": "integer"},
        },
    }
    config_schema = {"type": "object", "properties": {"base_url": {"type": "string"}, "default_headers": {"type": "object"}}}
    requires_capabilities = ["NETWORK"]

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        import time
        try:
            import httpx
        except ImportError:
            return BlockResult(ok=False, error="httpx not installed. Run: pip install httpx")

        try:
            url = str(inputs["url"])
            base_url = config.get("base_url", "")
            if base_url and not url.startswith("http"):
                url = base_url.rstrip("/") + "/" + url.lstrip("/")

            headers = {**config.get("default_headers", {}), **inputs.get("headers", {})}
            body = inputs.get("body", {})
            timeout = int(inputs.get("timeout_seconds", 30))

            start = time.monotonic()
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
            duration_ms = int((time.monotonic() - start) * 1000)

            return BlockResult(ok=resp.is_success, output={
                "status_code": resp.status_code,
                "body": resp.text[:100000],
                "headers": dict(resp.headers),
                "duration_ms": duration_ms,
            })
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "HTTP POST", "description": "Make a POST request with JSON body", "category": "HTTP", "display_icon": "📤", "display_color": "#0EA5E9", "input_schema": self.input_schema, "output_schema": self.output_schema}


class HTTPPutBlock(Block):
    id = "http.put"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "headers": {"type": "object"},
            "body": {"type": "object"},
            "timeout_seconds": {"type": "integer", "default": 30},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {"status_code": {"type": "integer"}, "body": {"type": "string"}, "duration_ms": {"type": "integer"}},
    }
    config_schema = {"type": "object", "properties": {"base_url": {"type": "string"}, "default_headers": {"type": "object"}}}
    requires_capabilities = ["NETWORK"]

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        import time
        try:
            import httpx
        except ImportError:
            return BlockResult(ok=False, error="httpx not installed")
        try:
            url = str(inputs["url"])
            base_url = config.get("base_url", "")
            if base_url and not url.startswith("http"):
                url = base_url.rstrip("/") + "/" + url.lstrip("/")
            headers = {**config.get("default_headers", {}), **inputs.get("headers", {})}
            timeout = int(inputs.get("timeout_seconds", 30))
            start = time.monotonic()
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.put(url, headers=headers, json=inputs.get("body", {}))
            duration_ms = int((time.monotonic() - start) * 1000)
            return BlockResult(ok=resp.is_success, output={"status_code": resp.status_code, "body": resp.text[:100000], "duration_ms": duration_ms})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "HTTP PUT", "description": "Make a PUT request", "category": "HTTP", "display_icon": "📤", "display_color": "#0EA5E9", "input_schema": self.input_schema, "output_schema": self.output_schema}


class HTTPDeleteBlock(Block):
    id = "http.delete"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "headers": {"type": "object"},
            "timeout_seconds": {"type": "integer", "default": 30},
        },
        "required": ["url"],
    }
    output_schema = {"type": "object", "properties": {"status_code": {"type": "integer"}, "body": {"type": "string"}, "duration_ms": {"type": "integer"}}}
    config_schema = {"type": "object", "properties": {"base_url": {"type": "string"}, "default_headers": {"type": "object"}}}
    requires_capabilities = ["NETWORK"]

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        import time
        try:
            import httpx
        except ImportError:
            return BlockResult(ok=False, error="httpx not installed")
        try:
            url = str(inputs["url"])
            base_url = config.get("base_url", "")
            if base_url and not url.startswith("http"):
                url = base_url.rstrip("/") + "/" + url.lstrip("/")
            headers = {**config.get("default_headers", {}), **inputs.get("headers", {})}
            timeout = int(inputs.get("timeout_seconds", 30))
            start = time.monotonic()
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.delete(url, headers=headers)
            duration_ms = int((time.monotonic() - start) * 1000)
            return BlockResult(ok=resp.is_success, output={"status_code": resp.status_code, "body": resp.text[:100000], "duration_ms": duration_ms})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "HTTP DELETE", "description": "Make a DELETE request", "category": "HTTP", "display_icon": "🗑️", "display_color": "#0EA5E9", "input_schema": self.input_schema, "output_schema": self.output_schema}
