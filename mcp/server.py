"""RIP MCP stdio server.

Start with:
    uv run python mcp/server.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS: dict[str, dict[str, Any]] = {
    "repo_search": {
        "description": (
            "Semantic search across the codebase. Finds code by meaning, "
            "not just keywords."
        ),
        "parameters": {
            "query": {"type": "string", "description": "What to search for"},
            "top_k": {
                "type": "integer",
                "description": "Number of results",
                "default": 10,
            },
        },
    },
    "repo_impact": {
        "description": "Find what depends on a symbol before changing it.",
        "parameters": {
            "symbol": {"type": "string", "description": "Class or function name"}
        },
    },
    "repo_trace": {
        "description": "Trace relationships and call chains from a symbol.",
        "parameters": {
            "symbol": {"type": "string", "description": "Starting symbol"}
        },
    },
    "repo_onboard": {
        "description": "Get a repository overview.",
        "parameters": {},
    },
    "repo_explain": {
        "description": "Explain how a feature or component works.",
        "parameters": {
            "topic": {"type": "string", "description": "What to explain"}
        },
    },
    "repo_architecture": {
        "description": "Generate the repository architecture diagram.",
        "parameters": {
            "format": {
                "type": "string",
                "description": "Output format: mermaid or json",
                "default": "mermaid",
            }
        },
    },
    "repo_metrics": {
        "description": "Show coupling and risk metrics.",
        "parameters": {
            "module": {
                "type": "string",
                "description": "Optional module path/name to inspect",
            },
            "top_risk": {
                "type": "integer",
                "description": "Optional number of top risk files to return",
            },
        },
    },
}


def run_rip_command(command: str, args: list[str] | None = None) -> str:
    """Run a RIP CLI command and return combined useful output."""
    cmd = ["uv", "run", "repo", command, *(args or [])]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).resolve().parent.parent),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out: repo {command}"
    except Exception as exc:  # noqa: BLE001 - MCP should return errors as text
        return f"Error running repo {command}: {exc}"

    output = result.stdout.strip()
    if result.returncode != 0 and result.stderr:
        warning = result.stderr.strip()[:1000]
        output = f"{output}\nWarning: {warning}".strip()
    return output or f"No output from repo {command}"


async def handle_tool_call(tool_name: str, parameters: dict[str, Any]) -> str:
    """Handle an MCP tool call and return text content."""
    if tool_name == "repo_search":
        query = str(parameters.get("query") or "")
        top_k = str(parameters.get("top_k") or 10)
        return run_rip_command("search", [query, "--limit", top_k])
    if tool_name == "repo_impact":
        return run_rip_command("impact", [str(parameters.get("symbol") or "")])
    if tool_name == "repo_trace":
        return run_rip_command("trace", [str(parameters.get("symbol") or "")])
    if tool_name == "repo_onboard":
        return run_rip_command("onboard")
    if tool_name == "repo_explain":
        return run_rip_command("explain", [str(parameters.get("topic") or "")])
    if tool_name == "repo_architecture":
        output_format = str(parameters.get("format") or "mermaid")
        return run_rip_command("architecture", ["--format", output_format])
    if tool_name == "repo_metrics":
        args: list[str] = []
        module = parameters.get("module")
        top_risk = parameters.get("top_risk")
        if module:
            args.extend(["--module", str(module)])
        if top_risk:
            args.extend(["--top-risk", str(top_risk)])
        return run_rip_command("metrics", args)
    return f"Unknown tool: {tool_name}"


def tools_list_response(request_id: Any) -> dict[str, Any]:
    tools = []
    for name, info in TOOLS.items():
        tools.append(
            {
                "name": name,
                "description": info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": info.get("parameters", {}),
                },
            }
        )
    return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}


async def dispatch(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method", "")
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "rip", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return tools_list_response(request_id)
    if method == "tools/call":
        params = request.get("params", {})
        result_text = await handle_tool_call(
            str(params.get("name") or ""),
            params.get("arguments") or {},
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": result_text}]},
        }
    if method == "notifications/initialized":
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


async def main() -> None:
    """Run a simple newline-delimited JSON-RPC stdio MCP server."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = await dispatch(request)
        except json.JSONDecodeError:
            continue
        except Exception as exc:  # noqa: BLE001 - protocol error response
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(exc)},
            }
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
