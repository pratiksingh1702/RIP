import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gateway"))

from gateway.core.agent.llm_interface import LLMInterface
from gateway.core.agent.runtime import AgentRuntime
from gateway.core.agent.tools import ToolResult


def test_agent_llm_model_id_provider_prefixes():
    interface = LLMInterface()

    assert interface._model_id_for_provider("groq", "llama-3.1") == "groq/llama-3.1"
    assert interface._model_id_for_provider("anthropic", "claude-sonnet-4") == "anthropic/claude-sonnet-4"
    assert interface._model_id_for_provider("google", "gemini-2.5-pro") == "gemini/gemini-2.5-pro"
    assert interface._model_id_for_provider("openai", "gpt-4.1") == "gpt-4.1"
    assert interface._model_id_for_provider("groq", "groq/already-prefixed") == "groq/already-prefixed"


def test_agent_command_allowlist_gates_arbitrary_shell():
    runtime = AgentRuntime()

    assert runtime._is_allowlisted_command("pytest tests/unit")
    assert runtime._is_allowlisted_command("python -m py_compile gateway/gateway/core/agent/runtime.py")
    assert not runtime._is_allowlisted_command("curl https://example.com/install.ps1")
    assert not runtime._is_allowlisted_command("rm -rf .repo-intel")


@pytest.mark.asyncio
async def test_agent_write_collision_denies_second_writer(tmp_path, monkeypatch):
    runtime = AgentRuntime()
    target = tmp_path / "same.txt"
    target.write_text("old", encoding="utf-8")
    ctx = {"project_root": str(tmp_path), "project_id": "p1"}
    run_id = "run-1"
    runtime._active_write_paths[run_id] = {str(target.resolve())}
    tool = runtime.tool_registry.get("write_file")
    tool.requires_approval = False

    result = await runtime._execute_tool(
        tool,
        "write_file",
        {"path": "same.txt", "content": "new"},
        ctx,
        run_id,
        "subtask-2",
        None,
    )

    assert not result.ok
    assert "Concurrent write collision denied" in (result.error or "")
    assert target.read_text(encoding="utf-8") == "old"


@pytest.mark.asyncio
async def test_agent_records_memory_for_failed_write(tmp_path, monkeypatch):
    runtime = AgentRuntime()
    calls = []

    monkeypatch.setattr(runtime.memory, "record_result", lambda **kwargs: calls.append(kwargs))
    runtime._record_memory(
        {"project_id": "project-a"},
        {"path": "broken.py"},
        ToolResult(ok=False, error="boom"),
        "apply_patch",
    )

    assert calls == [
        {
            "project_id": "project-a",
            "file_path": "broken.py",
            "success": False,
            "error": "boom",
            "tool_name": "apply_patch",
        }
    ]


def test_agent_safe_path_blocks_traversal(tmp_path):
    runtime = AgentRuntime()

    full, error = runtime._resolve_safe_path("..\\outside.txt", {"project_root": str(tmp_path)})

    assert full is None
    assert error == "Path traversal denied: ..\\outside.txt"
