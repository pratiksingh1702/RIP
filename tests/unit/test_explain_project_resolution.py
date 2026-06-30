from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from core.llm.models import ExplainIntent, ExplanationRequest
from server.routers import explain as explain_router


def test_resolve_explain_project_id_uses_repo_path_active_project(tmp_path):
    config_dir = tmp_path / ".repo-intel"
    config_dir.mkdir()
    (config_dir / "active_project").write_text("project-from-lib\n", encoding="utf-8")

    request = ExplanationRequest(query="typeProvider", repo_path=str(tmp_path))

    assert explain_router.resolve_explain_project_id(request) == "project-from-lib"


def test_resolve_explain_project_id_requires_project_id_or_repo_path():
    request = ExplanationRequest(query="typeProvider")

    with pytest.raises(HTTPException) as exc:
        explain_router.resolve_explain_project_id(request)

    assert exc.value.status_code == 400


def test_dependency_intent_is_available_for_cli_parity():
    assert ExplainIntent.DEPENDENCY.value == "dependency"


@pytest.mark.asyncio
async def test_explain_endpoint_uses_resolved_project_for_search_and_context(
    monkeypatch,
    tmp_path,
):
    config_dir = tmp_path / ".repo-intel"
    config_dir.mkdir()
    (config_dir / "active_project").write_text("lib-project\n", encoding="utf-8")

    calls: dict[str, object] = {}

    async def fake_get_project(db, project_id):
        calls["get_project"] = project_id
        return SimpleNamespace(id=project_id, name="lib", root=str(tmp_path))

    async def fake_verify_project_access(db, api_key, project_id):
        calls["verify_project"] = project_id
        return True

    class FakeSearcher:
        def __init__(self, **kwargs):
            calls["searcher_kwargs"] = kwargs

        async def hybrid_search(self, symbol, top_k, project_id):
            calls["search"] = {
                "symbol": symbol,
                "top_k": top_k,
                "project_id": project_id,
            }
            return ["result"]

    class FakeAssembler:
        def __init__(self, graph_client, project_id=None):
            calls["assembler_project"] = project_id

        def detect_intent(self, query):
            return SimpleNamespace(value="semantic")

        async def assemble_context(self, symbol, context_level, search_results=None):
            calls["assemble"] = {
                "symbol": symbol,
                "context_level": context_level,
                "search_results": search_results,
            }
            return SimpleNamespace(
                found=True,
                context_str="graph grounded context",
                intent=SimpleNamespace(value="semantic"),
                overview="`type_provider` is imported by **49 files**.",
                feature=None,
                important_entities=[{"name": "TypeNotifier"}],
                imported_files=[],
                important_files=[],
                api_endpoints=[],
                state_flow=[],
                suggestions=[
                    "Analyze dependencies of `TypeNotifier`: `repo impact TypeNotifier`"
                ],
            )

    async def fake_query_llm(user_prompt, system_prompt=None, provider=None, model=None):
        calls["prompt"] = user_prompt
        return "graph grounded answer"

    monkeypatch.setattr(explain_router, "get_project", fake_get_project)
    monkeypatch.setattr(explain_router, "verify_project_access", fake_verify_project_access)
    monkeypatch.setattr(explain_router, "Searcher", FakeSearcher)
    monkeypatch.setattr(explain_router, "ContextAssembler", FakeAssembler)
    monkeypatch.setattr(explain_router, "query_llm", fake_query_llm)

    http_request = SimpleNamespace(
        state=SimpleNamespace(api_key=None),
        app=SimpleNamespace(
            state=SimpleNamespace(
                runtime=SimpleNamespace(
                    neo4j=object(),
                    qdrant=object(),
                    embedder=object(),
                    reranker=object(),
                )
            )
        ),
    )
    request = ExplanationRequest(query="typeProvider", repo_path=str(tmp_path))

    response = await explain_router.explain_endpoint(
        http_request=http_request,
        request=request,
        db=object(),
    )

    assert response.success is True
    assert response.data["project_id"] == "lib-project"
    assert response.data["project_name"] == "lib"
    assert response.data["project_root"] == str(tmp_path)
    assert response.data["analysis_summary"]["overview"].startswith("`type_provider`")
    assert response.data["analysis_summary"]["key_entities"] == 1
    assert response.data["explanation"].startswith("## Analysis Summary")
    assert "`type_provider` is imported by **49 files**" in response.data["explanation"]
    assert "## Suggestions" in response.data["explanation"]
    assert response.data["suggested_improvements"] == [
        "Analyze dependencies of `TypeNotifier`: `repo impact TypeNotifier`"
    ]
    assert calls["search"]["project_id"] == "lib-project"
    assert calls["assembler_project"] == "lib-project"
    assert calls["assemble"]["search_results"] == ["result"]
    assert "graph grounded context" in calls["prompt"]


@pytest.mark.asyncio
async def test_explain_endpoint_rejects_unknown_project(monkeypatch):
    async def fake_get_project(db, project_id):
        return None

    monkeypatch.setattr(explain_router, "get_project", fake_get_project)

    http_request = SimpleNamespace(
        state=SimpleNamespace(api_key=None),
        app=SimpleNamespace(state=SimpleNamespace(runtime=SimpleNamespace())),
    )
    request = ExplanationRequest(query="typeProvider", project_id="missing")

    with pytest.raises(HTTPException) as exc:
        await explain_router.explain_endpoint(
            http_request=http_request,
            request=request,
            db=object(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_explain_endpoint_honors_cli_style_graph_flags(monkeypatch):
    calls: dict[str, object] = {"llm_called": False}

    async def fake_get_project(db, project_id):
        return SimpleNamespace(id=project_id, name="lib", root="C:/repo/lib")

    async def fake_verify_project_access(db, api_key, project_id):
        return True

    class FakeSearcher:
        def __init__(self, **kwargs):
            pass

        async def hybrid_search(self, symbol, top_k, project_id):
            return ["result"]

    class FakeAssembler:
        def __init__(self, graph_client, project_id=None):
            pass

        def detect_intent(self, query):
            return SimpleNamespace(value="flow")

        async def assemble_context(self, symbol, context_level, search_results=None):
            return SimpleNamespace(
                found=True,
                context_str="graph grounded context",
                overview="TypeNotifier is imported by 49 files.",
                feature=None,
                important_entities=[
                    {
                        "name": "TypeNotifier",
                        "type": "class",
                        "file_path": "type_provider.dart",
                        "raw_code": "class TypeNotifier {}",
                        "line_start": 10,
                        "line_end": 20,
                    }
                ],
                important_files=["type_provider.dart"],
                imported_files=[
                    {"target": "shared_preferences.dart", "is_external": False},
                    {"target": "package:flutter_riverpod/flutter_riverpod.dart", "is_external": True},
                ],
                api_endpoints=[],
                state_flow=[],
                workflow_chain=[
                    {"from": "TypeNotifier", "to": "setType", "relationship": "CALLS"}
                ],
                dependency_graph={
                    "TypeNotifier": [("SharedPreferences", "USES")]
                },
                suggestions=["Analyze dependencies of `TypeNotifier`: `repo impact TypeNotifier`"],
            )

    async def fake_query_llm(user_prompt, system_prompt=None, provider=None, model=None):
        calls["llm_called"] = True
        return "should not be called"

    monkeypatch.setattr(explain_router, "get_project", fake_get_project)
    monkeypatch.setattr(explain_router, "verify_project_access", fake_verify_project_access)
    monkeypatch.setattr(explain_router, "Searcher", FakeSearcher)
    monkeypatch.setattr(explain_router, "ContextAssembler", FakeAssembler)
    monkeypatch.setattr(explain_router, "query_llm", fake_query_llm)

    http_request = SimpleNamespace(
        state=SimpleNamespace(api_key=None),
        app=SimpleNamespace(
            state=SimpleNamespace(
                runtime=SimpleNamespace(
                    neo4j=object(),
                    qdrant=object(),
                    embedder=object(),
                    reranker=object(),
                )
            )
        ),
    )
    request = ExplanationRequest(
        query="how typeProvider works",
        project_id="lib-project",
        diagram=True,
        tree=True,
        dependencies=True,
        code=True,
        no_llm=True,
    )

    response = await explain_router.explain_endpoint(
        http_request=http_request,
        request=request,
        db=object(),
    )

    assert calls["llm_called"] is False
    assert response.success is True
    assert response.data["intent"] == "flow"
    assert response.data["flags"]["no_llm"] is True
    assert "## Workflow Tree" in response.data["explanation"]
    assert "```mermaid" in response.data["explanation"]
    assert "## Dependency Graph" in response.data["explanation"]
    assert "## Imported Files" in response.data["explanation"]
    assert "shared_preferences.dart" in response.data["explanation"]
    assert "## Relevant Code" in response.data["explanation"]
    assert "class TypeNotifier {}" in response.data["explanation"]
    assert "## Key Entities" in response.data["explanation"]
    assert response.data["imported_files"][0]["target"] == "shared_preferences.dart"
