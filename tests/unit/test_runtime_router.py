"""Runtime API tests."""

from __future__ import annotations

from types import SimpleNamespace

from server.routers.runtime import health


class FakeRuntime:
    def status(self) -> dict[str, object]:
        return {
            "neo4j_available": True,
            "qdrant_available": False,
        }


async def test_health_reports_runtime_readiness() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runtime=FakeRuntime())))

    response = await health(request)

    assert response == {
        "status": "ready",
        "neo4j": True,
        "qdrant": False,
    }
