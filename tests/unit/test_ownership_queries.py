"""Ownership query tests."""

from __future__ import annotations

from core.graph.queries.ownership import (
    create_developers_and_commits_batch,
    relate_commits_to_files_batch,
    set_file_ownership_batch,
)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(
        self,
        query: str,
        parameters: dict[str, object] | None = None,
    ) -> list[dict[str, object]]:
        self.calls.append((query, parameters or {}))
        return []


async def test_create_developers_and_commits_uses_single_unwind_query() -> None:
    client = FakeClient()
    rows = [
        {
            "hash": "abc",
            "message": "initial",
            "timestamp": "2026-06-24T10:00:00",
            "author_name": "A User",
            "author_email": "a@example.com",
        },
        {
            "hash": "def",
            "message": "next",
            "timestamp": "2026-06-24T11:00:00",
            "author_name": "B User",
            "author_email": "b@example.com",
        },
    ]

    await create_developers_and_commits_batch(client, rows)

    assert len(client.calls) == 1
    query, parameters = client.calls[0]
    assert "UNWIND $rows AS row" in query
    assert "MERGE (d)-[:AUTHORED]->(c)" in query
    assert parameters == {"rows": rows}


async def test_file_and_ownership_batches_use_analysis_relationship_names() -> None:
    client = FakeClient()

    await relate_commits_to_files_batch(
        client,
        [{"hash": "abc", "file_path": "/repo/app.py"}],
        "project-a",
    )
    await set_file_ownership_batch(
        client,
        [
            {
                "file_path": "/repo/app.py",
                "author_email": "a@example.com",
                "author_name": "A User",
                "percentage": 75.0,
                "line_count": 30,
            }
        ],
        "project-a",
    )

    assert "MERGE (c)-[:MODIFIES]->(f)" in client.calls[0][0]
    assert "MERGE (f)-[r:OWNED_BY]->(d)" in client.calls[1][0]
