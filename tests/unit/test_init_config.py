"""Init command config tests."""

from __future__ import annotations

import tomllib

from cli.commands.init import init


def test_init_writes_project_name_and_isolation_config(tmp_path) -> None:
    init(
        tmp_path,
        project_name="billing-api",
        isolation=True,
        qdrant_strategy="payload_filter",
    )

    config_path = tmp_path / ".repo-intel" / "config.toml"
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    assert data["project"]["name"] == "billing-api"
    assert data["project"]["id"]
    assert data["project"]["root"] == tmp_path.as_posix()
    assert data["isolation"]["enabled"] is True
    assert data["isolation"]["qdrant_strategy"] == "payload_filter"
    assert data["isolation"]["require_project_filter"] is True
