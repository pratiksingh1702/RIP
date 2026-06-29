from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.projects import list_projects, verify_project_access
from core.storage.models import ApiKey, Project


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _ScalarResult(self._values)


class _ProjectVisibilitySession:
    def __init__(self, projects: list[Project], api_keys: list[ApiKey]):
        self.projects = projects
        self.api_keys = api_keys

    async def execute(self, statement):
        statement_text = str(statement)
        if "FROM api_keys" in statement_text:
            restricted_ids = [
                api_key.project_id
                for api_key in self.api_keys
                if api_key.is_active and api_key.project_id is not None
            ]
            return _ExecuteResult(restricted_ids)
        if "FROM projects" in statement_text:
            return _ExecuteResult(self.projects)
        raise AssertionError(f"Unexpected statement: {statement_text}")


def _project(project_id: str) -> Project:
    return Project(
        id=project_id,
        name=project_id.title(),
        language="python",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        files_count=1,
        entities_count=1,
        languages=["python"],
        indexed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _api_key(project_id: str | None, *, active: bool = True) -> ApiKey:
    return ApiKey(
        name=f"key-{project_id or 'public'}",
        key_hash=f"hash-{project_id or 'public'}",
        prefix="rip_test",
        is_active=active,
        project_id=project_id,
    )


@pytest.mark.asyncio
async def test_authenticated_project_list_sees_all_open_projects():
    session = _ProjectVisibilitySession(
        projects=[_project("lib"), _project("rip")],
        api_keys=[_api_key("lib"), _api_key("rip")],
    )

    visible = await list_projects(session, is_global=True)

    assert [project.id for project in visible] == ["lib", "rip"]


@pytest.mark.asyncio
async def test_development_scope_can_still_see_all_projects():
    session = _ProjectVisibilitySession(
        projects=[_project("public"), _project("linked")],
        api_keys=[_api_key("linked")],
    )

    visible = await list_projects(session, associated_project_id=None, is_global=True)

    assert [project.id for project in visible] == ["public", "linked"]


@pytest.mark.asyncio
async def test_valid_api_key_can_access_any_open_project():
    session = _ProjectVisibilitySession(
        projects=[_project("public"), _project("linked"), _project("other")],
        api_keys=[_api_key("linked"), _api_key("other")],
    )
    linked_key = _api_key("linked")
    linked_key._rip_access_scope = "all"

    assert await verify_project_access(session, linked_key, "public") is True
    assert await verify_project_access(session, linked_key, "linked") is True
    assert await verify_project_access(session, linked_key, "other") is True


@pytest.mark.asyncio
async def test_development_access_scope_allows_all_projects():
    session = _ProjectVisibilitySession(
        projects=[_project("public"), _project("linked")],
        api_keys=[_api_key("linked")],
    )
    dev_key = _api_key(None)
    dev_key._rip_access_scope = "all"

    assert await verify_project_access(session, dev_key, "linked") is True
