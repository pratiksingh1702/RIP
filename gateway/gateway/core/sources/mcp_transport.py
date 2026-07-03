"""Universal MCP client helpers for runtime-configured Gateway sources."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx


@dataclass(slots=True)
class MCPToolInfo:
    """Discovered MCP tool metadata."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


@dataclass(slots=True)
class MCPHandshake:
    """Result of connecting to an MCP server and listing tools."""

    tools: list[MCPToolInfo]
    server_info: dict[str, Any]


@dataclass(slots=True)
class MCPCallResult:
    """Normalized result from an MCP tools/call request."""

    content: str
    raw_result: Any


class MCPProtocolError(RuntimeError):
    """Raised when a server is reachable but does not speak the expected MCP shape."""


class MCPConfigError(ValueError):
    """Raised for unsafe or incomplete user-provided MCP source configuration."""


class UniversalMCPClient:
    """Small server-side MCP client for stdio, streamable HTTP, and SSE transports."""

    def __init__(
        self,
        *,
        transport: str,
        endpoint_url: str | None,
        headers: dict[str, str],
        mcp_config: dict[str, Any],
        timeout_seconds: float,
        output_limit: int = 120_000,
    ):
        self.transport = _normalize_transport(transport)
        self.endpoint_url = (endpoint_url or "").rstrip("/")
        self.headers = headers
        self.mcp_config = dict(mcp_config or {})
        self.timeout_seconds = timeout_seconds
        self.output_limit = output_limit
        self._request_id = int(time.time() * 1000)

    async def handshake(self) -> MCPHandshake:
        """Initialize the MCP connection and list available tools."""
        if self.transport == "stdio":
            return await self._stdio_handshake()
        if self.transport == "sse":
            return await self._sse_handshake()
        return await self._http_handshake()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPCallResult:
        """Call one MCP tool and normalize the result text."""
        if self.transport == "stdio":
            return await self._stdio_call_tool(tool_name, arguments)
        if self.transport == "sse":
            return await self._sse_call_tool(tool_name, arguments)
        return await self._http_call_tool(tool_name, arguments)

    async def _http_handshake(self) -> MCPHandshake:
        initialize = await self._http_request("initialize", self._initialize_params())
        await self._http_notification("notifications/initialized", {})
        tools_result = await self._http_request("tools/list", {})
        return MCPHandshake(
            tools=_tools_from_result(tools_result),
            server_info=_server_info_from_initialize(initialize),
        )

    async def _http_call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPCallResult:
        result = await self._http_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
        return MCPCallResult(content=_extract_content(result), raw_result=result)

    async def _http_request(self, method: str, params: dict[str, Any]) -> Any:
        if not self.endpoint_url:
            raise MCPConfigError("MCP endpoint URL is required")
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint_url,
                json=payload,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                    **self.headers,
                },
            )
        return _jsonrpc_result(response)

    async def _http_notification(self, method: str, params: dict[str, Any]) -> None:
        if not self.endpoint_url:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout_seconds, 5.0)) as client:
                await client.post(
                    self.endpoint_url,
                    json=payload,
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        **self.headers,
                    },
                )
        except Exception:
            return

    async def _sse_handshake(self) -> MCPHandshake:
        sdk_result = await self._try_sdk_sse("handshake")
        if isinstance(sdk_result, MCPHandshake):
            return sdk_result
        return await self._http_handshake()

    async def _sse_call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPCallResult:
        sdk_result = await self._try_sdk_sse("call_tool", tool_name, arguments)
        if isinstance(sdk_result, MCPCallResult):
            return sdk_result
        return await self._http_call_tool(tool_name, arguments)

    async def _try_sdk_sse(
        self,
        action: str,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> MCPHandshake | MCPCallResult | None:
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except Exception:
            return None
        if not self.endpoint_url:
            raise MCPConfigError("MCP SSE endpoint URL is required")
        try:
            async with sse_client(self.endpoint_url, headers=self.headers) as streams:
                async with ClientSession(*streams) as session:
                    init = await session.initialize()
                    if action == "handshake":
                        tools = await session.list_tools()
                        return MCPHandshake(
                            tools=_tools_from_sdk(tools),
                            server_info=_sdk_model_dump(init),
                        )
                    result = await session.call_tool(tool_name or "search", arguments or {})
                    return MCPCallResult(content=_extract_content(_sdk_model_dump(result)), raw_result=_sdk_model_dump(result))
        except Exception:
            return None

    async def _stdio_handshake(self) -> MCPHandshake:
        sdk_result = await self._try_sdk_stdio("handshake")
        if isinstance(sdk_result, MCPHandshake):
            return sdk_result
        return await self._stdio_line_json_handshake()

    async def _stdio_call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPCallResult:
        sdk_result = await self._try_sdk_stdio("call_tool", tool_name, arguments)
        if isinstance(sdk_result, MCPCallResult):
            return sdk_result
        return await self._stdio_line_json_call_tool(tool_name, arguments)

    async def _try_sdk_stdio(
        self,
        action: str,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> MCPHandshake | MCPCallResult | None:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except Exception:
            return None
        command, args, cwd, env = self._stdio_process_config()
        params = StdioServerParameters(command=command, args=args, cwd=cwd, env=env)
        try:
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    init = await session.initialize()
                    if action == "handshake":
                        tools = await session.list_tools()
                        return MCPHandshake(
                            tools=_tools_from_sdk(tools),
                            server_info=_sdk_model_dump(init),
                        )
                    result = await session.call_tool(tool_name or "search", arguments or {})
                    dumped = _sdk_model_dump(result)
                    return MCPCallResult(content=_extract_content(dumped), raw_result=dumped)
        except Exception:
            return None

    async def _stdio_line_json_handshake(self) -> MCPHandshake:
        responses = await self._run_stdio_line_json(
            [
                ("initialize", self._initialize_params()),
                ("tools/list", {}),
            ]
        )
        initialize = responses[0] if responses else {}
        tools_result = responses[1] if len(responses) > 1 else {}
        return MCPHandshake(
            tools=_tools_from_result(tools_result),
            server_info=_server_info_from_initialize(initialize),
        )

    async def _stdio_line_json_call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPCallResult:
        responses = await self._run_stdio_line_json(
            [("tools/call", {"name": tool_name, "arguments": arguments})]
        )
        result = responses[0] if responses else {}
        return MCPCallResult(content=_extract_content(result), raw_result=result)

    async def _run_stdio_line_json(self, calls: list[tuple[str, dict[str, Any]]]) -> list[Any]:
        command, args, cwd, env = self._stdio_process_config()
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            cwd=cwd,
            env={**os.environ, **env},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        responses: list[Any] = []
        try:
            for method, params in calls:
                payload = {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": method,
                    "params": params,
                }
                process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
                await process.stdin.drain()
                line = await asyncio.wait_for(process.stdout.readline(), timeout=self.timeout_seconds)
                if not line:
                    raise MCPProtocolError("stdio MCP server closed without a response")
                responses.append(_result_from_json(json.loads(line.decode("utf-8"))))
            return responses
        finally:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except Exception:
                process.kill()

    def _stdio_process_config(self) -> tuple[str, list[str], str | None, dict[str, str]]:
        command = str(self.mcp_config.get("stdio_command") or "").strip()
        if not command:
            raise MCPConfigError("stdio_command is required for stdio MCP sources")
        if _contains_shell_control(command):
            raise MCPConfigError("stdio_command must be a single executable, not a shell command")
        args = self.mcp_config.get("stdio_args") or []
        if not isinstance(args, list):
            raise MCPConfigError("stdio_args must be a list")
        normalized_args = [str(arg) for arg in args]
        if any(_contains_shell_control(arg) for arg in normalized_args):
            raise MCPConfigError("stdio_args cannot contain shell control operators")
        cwd = self.mcp_config.get("stdio_cwd")
        cwd = str(cwd).strip() if cwd else None
        env_raw = self.mcp_config.get("stdio_env") or {}
        if not isinstance(env_raw, dict):
            raise MCPConfigError("stdio_env must be an object")
        env = {str(key): str(value) for key, value in env_raw.items()}
        return command, normalized_args, cwd, env

    def _initialize_params(self) -> dict[str, Any]:
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "rip-gateway", "version": "1.0.0"},
        }

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id


def _normalize_transport(transport: str) -> str:
    value = (transport or "streamable_http").lower()
    if value == "http":
        return "streamable_http"
    if value not in {"streamable_http", "sse", "stdio"}:
        raise MCPConfigError(f"Unsupported MCP transport: {transport}")
    return value


def _contains_shell_control(value: str) -> bool:
    return bool(re.search(r"&&|\|\||[;|<>`]", value))


def _jsonrpc_result(response: httpx.Response) -> Any:
    if response.status_code in {401, 403}:
        raise PermissionError("MCP source authentication failed")
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    text = response.text[:120_000]
    if "text/event-stream" in content_type:
        return _result_from_sse(text)
    try:
        return _result_from_json(response.json())
    except ValueError as exc:
        raise MCPProtocolError("MCP server returned non-JSON response") from exc


def _result_from_sse(text: str) -> Any:
    data_lines = []
    for line in text.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not data_lines:
        raise MCPProtocolError("MCP SSE response did not contain data")
    return _result_from_json(json.loads("\n".join(data_lines)))


def _result_from_json(data: dict[str, Any]) -> Any:
    if "error" in data and data["error"]:
        error = data["error"]
        if isinstance(error, dict):
            raise MCPProtocolError(str(error.get("message") or error))
        raise MCPProtocolError(str(error))
    if "result" not in data:
        raise MCPProtocolError("MCP response missing result")
    return data["result"]


def _tools_from_result(result: Any) -> list[MCPToolInfo]:
    payload = result or {}
    tools = payload.get("tools", payload if isinstance(payload, list) else [])
    output = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        output.append(
            MCPToolInfo(
                name=str(tool.get("name") or ""),
                description=tool.get("description"),
                input_schema=tool.get("inputSchema") or tool.get("input_schema"),
            )
        )
    return [tool for tool in output if tool.name]


def _tools_from_sdk(tools_result: Any) -> list[MCPToolInfo]:
    dumped = _sdk_model_dump(tools_result)
    return _tools_from_result(dumped)


def _sdk_model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, list):
        return [_sdk_model_dump(item) for item in value]
    return value


def _server_info_from_initialize(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result.get("serverInfo") or result.get("server_info") or {}
    return {}


def _extract_content(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        return "\n".join(filter(None, (_extract_content(item) for item in result)))
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            return "\n".join(filter(None, (_extract_content(item) for item in content)))
        if isinstance(content, str):
            return content
        for key in ("text", "message", "result"):
            value = result.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, (dict, list)):
                extracted = _extract_content(value)
                if extracted:
                    return extracted
    return json.dumps(result, default=str)
