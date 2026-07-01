r"""RIP MCP stdio server.

Start with:
    uv run python mcp/server.py [repo_path]

Configure in Codex:
    Name: RIP
    Type: STDIO
    Command: C:\Users\Dell\Downloads\RIP\.venv\Scripts\python.exe
    Args: mcp/server.py C:\Users\Dell\Downloads\untitled2\untitled2\lib
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from rich.console import Console


RIP_PATH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RIP_PATH))

REPO_PATH = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
os.chdir(REPO_PATH)


def prop(type_: str, description: str, default: Any = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": type_, "description": description}
    if default is not None:
        schema["default"] = default
    return schema


TOOLS: dict[str, dict[str, Any]] = {
    "repo_init": {
        "description": "Initialize a repository for RIP indexing and write .repo-intel/config.toml.",
        "parameters": {
            "repo_path": prop("string", "Repository path to initialize.", "."),
            "project_name": prop("string", "Project name stored in .repo-intel/config.toml."),
            "isolation": prop("boolean", "Enable repository isolation filters.", True),
            "qdrant_strategy": prop(
                "string",
                "Qdrant isolation strategy: payload_filter or collection_per_project.",
                "payload_filter",
            ),
        },
    },
    "repo_index": {
        "description": (
            "Index a repository's codebase, building the Neo4j knowledge graph and "
            "Qdrant semantic search index. May take time on large projects."
        ),
        "parameters": {
            "repo_path": prop("string", "Repository path to index.", "."),
            "watch": prop(
                "boolean",
                "Watch files and re-index on save. Refused unless allow_long_running is true.",
                False,
            ),
            "incremental": prop("boolean", "Index only changed files instead of a full index.", False),
            "languages": prop("string", "Comma-separated languages to restrict indexing."),
            "verbose": prop("boolean", "Show detailed runtime logs and write .repo-intel/logs output.", False),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
            "allow_long_running": prop(
                "boolean",
                "Allow long-running index modes such as --watch.",
                False,
            ),
        },
    },
    "repo_trace": {
        "description": "Trace call graph relationships from an entry point.",
        "parameters": {
            "entry_point": prop("string", "Function or symbol to trace."),
            "depth": prop("integer", "Trace depth.", 10),
            "format": prop("string", "Output format: text or json.", "text"),
            "project": prop("string", "Project id override."),
            "explain": prop("boolean", "Generate an explanation for the call path.", False),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
        },
    },
    "repo_impact": {
        "description": "Analyze which files, APIs, and symbols may be affected by changing a symbol or file.",
        "parameters": {
            "symbol": prop("string", "Symbol or file to analyze."),
            "format": prop("string", "Output format: text or json.", "text"),
            "project": prop("string", "Project id override."),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
        },
    },
    "repo_explain": {
        "description": (
            "Generate architecture-aware explanations with optional Mermaid diagram, "
            "workflow tree, dependency table, and LLM context."
        ),
        "parameters": {
            "topic": prop("string", "What to explain: symbol name or natural-language query."),
            "level": prop("string", "Context level: file, class, or function.", "file"),
            "provider": prop(
                "string",
                "LLM provider override, e.g. google, openrouter, openai, anthropic, ollama.",
            ),
            "model": prop("string", "LLM model override, e.g. gemini-2.5-flash."),
            "project": prop("string", "Project id override."),
            "diagram": prop("boolean", "Show Mermaid workflow diagram.", False),
            "tree": prop("boolean", "Show Rich workflow tree.", False),
            "deps": prop("boolean", "Show dependency table.", False),
            "no_llm": prop("boolean", "Skip LLM generation and show graph analysis only.", True),
            "max_hops": prop("integer", "Maximum workflow trace hops.", 8),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
        },
    },
    "repo_search": {
        "description": "Semantic search across indexed code entities by natural language or symbol name.",
        "parameters": {
            "query": prop("string", "Semantic search query."),
            "limit": prop("integer", "Number of results to return.", 20),
            "language": prop("string", "Filter results to a specific language."),
            "service": prop("string", "Filter results to a specific service."),
            "entity_type": prop("string", "Filter by entity type, e.g. function, class, widget."),
            "project": prop("string", "Project id override."),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
        },
    },
    "repo_projects": {
        "description": "List indexed projects known to RIP.",
        "parameters": {},
    },
    "repo_use": {
        "description": "Set the active project id for subsequent project-scoped commands.",
        "parameters": {
            "project_id": prop("string", "Project id to activate."),
            "repo_path": prop("string", "Repository folder where .repo-intel/active_project is stored.", "."),
        },
    },
    "repo_dead_code": {
        "description": "Identify unused functions and classes in the indexed codebase.",
        "parameters": {
            "type": prop("string", "Entity type to check: functions, classes, or all.", "all"),
            "format": prop("string", "Output format: text or json.", "text"),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
        },
    },
    "repo_onboard": {
        "description": "Generate a repository onboarding guide from indexed architecture data.",
        "parameters": {
            "output": prop("string", "Optional file path to save the guide."),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
        },
    },
    "repo_architecture": {
        "description": "Visualize repository architecture as Mermaid or JSON.",
        "parameters": {
            "format": prop("string", "Output format: mermaid or json.", "mermaid"),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
        },
    },
    "repo_metrics": {
        "description": "Show coupling, complexity, risk, and git activity metrics.",
        "parameters": {
            "module": prop("string", "Specific module/file to inspect."),
            "top_risk": prop("integer", "Show the top N high-risk modules."),
            "mode": prop("string", "Runtime mode: auto, server, or local.", "auto"),
        },
    },
    "repo_serve": {
        "description": (
            "Start the RIP FastAPI server. By default this starts a background process "
            "and returns immediately."
        ),
        "parameters": {
            "host": prop("string", "Host to bind.", "localhost"),
            "port": prop("integer", "Port to bind.", 8000),
            "reload": prop("boolean", "Enable auto-reload for development.", False),
            "background": prop("boolean", "Start as a background process and return PID.", True),
            "mode": prop("string", "Runtime mode: server or local.", "server"),
        },
    },
    "repo_status": {
        "description": "Check indexing status for a repository.",
        "parameters": {
            "repo_path": prop("string", "Repository path to check.", "."),
        },
    },
    "repo_delete": {
        "description": (
            "Delete RIP indexed data from Neo4j, Qdrant, and/or storage. Destructive: "
            "requires yes=true."
        ),
        "parameters": {
            "project": prop("string", "Delete only one indexed project id; omit to delete all RIP data."),
            "yes": prop("boolean", "Required confirmation flag. Must be true to run.", False),
            "neo4j": prop("boolean", "Clear Neo4j graph data.", True),
            "qdrant": prop("boolean", "Delete Qdrant vector collection/points.", True),
            "storage": prop("boolean", "Reset RIP metadata tables/rows.", True),
            "mode": prop("string", "Runtime mode: server or local.", "server"),
        },
    },
    "repo_config": {
        "description": "Show or modify configuration settings. Currently not implemented by the CLI.",
        "parameters": {},
    },
}


def _value(parameters: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in parameters and parameters[name] is not None:
            return parameters[name]
    return default


def _path(value: Any, default: str = ".") -> Path:
    return Path(str(value or default)).expanduser()


def _patch_console(module: Any, stdout: io.StringIO) -> None:
    if hasattr(module, "console"):
        module.console = Console(file=stdout, force_terminal=False, color_system=None)


async def _run_captured(action: Callable[[], None]) -> str:
    old_stdout = sys.stdout
    stdout = io.StringIO()
    sys.stdout = stdout
    try:
        await asyncio.to_thread(action)
    except Exception as exc:
        import traceback

        return f"Error: {exc}\n\nTraceback:\n{traceback.format_exc()}"
    finally:
        with contextlib.suppress(Exception):
            output = stdout.getvalue()
        sys.stdout = old_stdout
    return output.strip() or "Command completed (no output)"


async def _serve_tool(parameters: dict[str, Any]) -> str:
    host = str(_value(parameters, "host", default="localhost"))
    port = int(_value(parameters, "port", default=8000))
    reload = bool(_value(parameters, "reload", default=False))
    background = bool(_value(parameters, "background", default=True))

    if not background:
        import cli.commands.serve as serve_module

        return await _run_captured(
            lambda: serve_module.serve(
                host=host,
                port=port,
                reload=reload,
                mode=str(_value(parameters, "mode", default="server")),
            )
        )

    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "server.app:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        args.append("--reload")
    process = subprocess.Popen(  # noqa: S603 - local server helper for MCP.
        args,
        cwd=str(RIP_PATH),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return f"Started RIP API server on http://{host}:{port} (pid {process.pid})."


async def handle_tool_call(tool_name: str, parameters: dict[str, Any]) -> str:
    """Handle MCP tool call using the same command modules as the CLI."""
    parameters = parameters or {}

    if tool_name == "repo_serve":
        return await _serve_tool(parameters)

    if tool_name == "repo_config":
        return "repo config is not implemented yet."

    if tool_name == "repo_delete" and not bool(_value(parameters, "yes", default=False)):
        return "Refusing destructive delete. Pass yes=true to confirm."

    if tool_name == "repo_index" and bool(_value(parameters, "watch", default=False)) and not bool(
        _value(parameters, "allow_long_running", default=False)
    ):
        return "Refusing long-running repo index --watch. Pass allow_long_running=true to run it."

    async def run(action: Callable[[], None], modules: list[Any] | None = None) -> str:
        old_stdout = sys.stdout
        stdout = io.StringIO()
        sys.stdout = stdout
        try:
            for module in modules or []:
                _patch_console(module, stdout)
            await asyncio.to_thread(action)
        except Exception as exc:
            import traceback

            return f"Error: {exc}\n\nTraceback:\n{traceback.format_exc()}"
        finally:
            with contextlib.suppress(Exception):
                output = stdout.getvalue()
            sys.stdout = old_stdout
        return output.strip() or "Command completed (no output)"

    if tool_name == "repo_init":
        import cli.commands.init as mod

        return await run(
            lambda: mod.init(
                repo_path=_path(_value(parameters, "repo_path", default=".")),
                project_name=_value(parameters, "project_name"),
                isolation=bool(_value(parameters, "isolation", default=True)),
                qdrant_strategy=str(_value(parameters, "qdrant_strategy", default="payload_filter")),
            ),
            [mod],
        )

    if tool_name == "repo_index":
        import cli.commands.index as mod

        return await run(
            lambda: mod.index(
                repo_path=_path(_value(parameters, "repo_path", default=".")),
                watch=bool(_value(parameters, "watch", default=False)),
                incremental=bool(_value(parameters, "incremental", default=False)),
                languages=_value(parameters, "languages"),
                verbose=bool(_value(parameters, "verbose", default=False)),
                mode=str(_value(parameters, "mode", default="auto")),
            ),
            [mod],
        )

    if tool_name == "repo_trace":
        from cli.commands.trace import trace

        return await run(
            lambda: trace(
                entry_point=str(_value(parameters, "entry_point", "symbol", default="")),
                depth=int(_value(parameters, "depth", default=10)),
                output_format=str(_value(parameters, "format", "output_format", default="text")),
                explain=bool(_value(parameters, "explain", default=False)),
                project=_value(parameters, "project"),
                mode=str(_value(parameters, "mode", default="auto")),
            )
        )

    if tool_name == "repo_impact":
        from cli.commands.impact import impact

        return await run(
            lambda: impact(
                symbol=str(_value(parameters, "symbol", default="")),
                output_format=str(_value(parameters, "format", "output_format", default="text")),
                project=_value(parameters, "project"),
                mode=str(_value(parameters, "mode", default="auto")),
            )
        )

    if tool_name == "repo_explain":
        import cli.commands.explain as mod

        return await run(
            lambda: mod.explain(
                symbol=str(_value(parameters, "topic", "symbol", default="")),
                context_level=str(_value(parameters, "level", "context_level", default="file")),
                provider=_value(parameters, "provider"),
                model=_value(parameters, "model"),
                project=_value(parameters, "project"),
                diagram=bool(_value(parameters, "diagram", default=False)),
                tree_view=bool(_value(parameters, "tree", "tree_view", default=False)),
                dependencies=bool(_value(parameters, "deps", "dependencies", default=False)),
                no_llm=bool(_value(parameters, "no_llm", default=True)),
                max_hops=int(_value(parameters, "max_hops", default=8)),
                mode=str(_value(parameters, "mode", default="auto")),
            ),
            [mod],
        )

    if tool_name == "repo_search":
        import cli.commands.search as mod

        return await run(
            lambda: mod.search(
                query=str(_value(parameters, "query", default="")),
                limit=int(_value(parameters, "limit", "top_k", default=20)),
                language=_value(parameters, "language"),
                service=_value(parameters, "service"),
                entity_type=_value(parameters, "entity_type"),
                project=_value(parameters, "project"),
                mode=str(_value(parameters, "mode", default="auto")),
            ),
            [mod],
        )

    if tool_name == "repo_projects":
        import cli.commands.projects as mod

        return await run(mod.projects, [mod])

    if tool_name == "repo_use":
        import cli.commands.projects as mod

        return await run(
            lambda: mod.use(
                project_id=str(_value(parameters, "project_id", "project", default="")),
                repo_path=_path(_value(parameters, "repo_path", default=".")),
            ),
            [mod],
        )

    if tool_name == "repo_dead_code":
        import cli.commands.dead_code as mod

        return await run(
            lambda: mod.dead_code(
                entity_type=str(_value(parameters, "type", "entity_type", default="all")),
                output_format=str(_value(parameters, "format", "output_format", default="text")),
                mode=str(_value(parameters, "mode", default="auto")),
            ),
            [mod],
        )

    if tool_name == "repo_onboard":
        import cli.commands.onboard as mod

        output = _value(parameters, "output")
        return await run(
            lambda: mod.onboard(
                output=Path(str(output)) if output else None,
                mode=str(_value(parameters, "mode", default="auto")),
            ),
            [mod],
        )

    if tool_name == "repo_architecture":
        import cli.commands.architecture as mod

        return await run(
            lambda: mod.architecture(
                output_format=str(_value(parameters, "format", "output_format", default="mermaid")),
                mode=str(_value(parameters, "mode", default="auto")),
            ),
            [mod],
        )

    if tool_name == "repo_metrics":
        import cli.commands.metrics as mod

        top_risk = _value(parameters, "top_risk")
        return await run(
            lambda: mod.metrics(
                module=_value(parameters, "module"),
                top_risk=int(top_risk) if top_risk is not None else None,
                mode=str(_value(parameters, "mode", default="auto")),
            ),
            [mod],
        )

    if tool_name == "repo_status":
        import cli.commands.status as mod

        return await run(
            lambda: mod.status(repo_path=_path(_value(parameters, "repo_path", default="."))),
            [mod],
        )

    if tool_name == "repo_delete":
        import cli.commands.delete as mod

        return await run(
            lambda: mod.delete(
                project=_value(parameters, "project"),
                yes=True,
                neo4j=bool(_value(parameters, "neo4j", default=True)),
                qdrant=bool(_value(parameters, "qdrant", default=True)),
                storage=bool(_value(parameters, "storage", default=True)),
                mode=str(_value(parameters, "mode", default="server")),
            ),
            [mod],
        )

    return f"Unknown tool: {tool_name}"


def tools_list_response(request_id: Any) -> dict[str, Any]:
    tools = [
        {
            "name": name,
            "description": info["description"],
            "inputSchema": {
                "type": "object",
                "properties": info.get("parameters", {}),
            },
        }
        for name, info in TOOLS.items()
    ]
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
                "serverInfo": {
                    "name": "rip",
                    "version": "1.0.0",
                    "description": f"Repository Intelligence - indexed at {REPO_PATH}",
                },
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
    print("RIP MCP Server starting...", file=sys.stderr, flush=True)
    print(f"Repo path: {REPO_PATH}", file=sys.stderr, flush=True)
    print(f"Available tools: {list(TOOLS.keys())}", file=sys.stderr, flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = await dispatch(request)
        except json.JSONDecodeError:
            continue
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(exc)},
            }
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
