"""Neo4j schema setup."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.graph.client import Neo4jClient

logger = logging.getLogger(__name__)

PRE_SCHEMA_STATEMENTS = [
    "DROP CONSTRAINT module_project_name_unique IF EXISTS",
]

SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
    (
        "CREATE CONSTRAINT file_project_path_unique IF NOT EXISTS "
        "FOR (f:File) REQUIRE (f.project_id, f.path) IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT function_project_fqn_unique IF NOT EXISTS "
        "FOR (fn:Function) REQUIRE (fn.project_id, fn.fqn) IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT class_project_fqn_unique IF NOT EXISTS "
        "FOR (c:Class) REQUIRE (c.project_id, c.fqn) IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT widget_project_fqn_unique IF NOT EXISTS "
        "FOR (w:Widget) REQUIRE (w.project_id, w.fqn) IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT module_project_key_unique IF NOT EXISTS "
        "FOR (m:Module) REQUIRE (m.project_id, m.module_key) IS UNIQUE"
    ),
    "CREATE INDEX function_name IF NOT EXISTS FOR (fn:Function) ON (fn.name)",
    "CREATE INDEX class_project IF NOT EXISTS FOR (c:Class) ON (c.project_id)",
    "CREATE INDEX widget_project IF NOT EXISTS FOR (w:Widget) ON (w.project_id)",
    "CREATE INDEX module_project IF NOT EXISTS FOR (m:Module) ON (m.project_id)",
    "CREATE INDEX file_project IF NOT EXISTS FOR (f:File) ON (f.project_id)",
    "CREATE INDEX file_language IF NOT EXISTS FOR (f:File) ON (f.language)",
]


async def setup_schema(client: Neo4jClient, progress: object | None = None) -> None:
    total = len(PRE_SCHEMA_STATEMENTS) + len(SCHEMA_STATEMENTS)
    current = 0
    for statement in PRE_SCHEMA_STATEMENTS:
        current += 1
        _update_schema_progress(progress, current, total, statement)
        start = time.perf_counter()
        logger.info("Neo4j schema step %s/%s starting: %s", current, total, statement)
        await client.execute(statement)
        logger.info(
            "Neo4j schema step %s/%s finished in %.2fs",
            current,
            total,
            time.perf_counter() - start,
        )
    for statement in SCHEMA_STATEMENTS:
        current += 1
        _update_schema_progress(progress, current, total, statement)
        start = time.perf_counter()
        logger.info("Neo4j schema step %s/%s starting: %s", current, total, statement)
        await client.execute(statement)
        logger.info(
            "Neo4j schema step %s/%s finished in %.2fs",
            current,
            total,
            time.perf_counter() - start,
        )


def _update_schema_progress(
    progress: Any | None,
    current: int,
    total: int,
    statement: str,
) -> None:
    if progress is None:
        return
    progress.current_stage = "Preparing graph"
    progress.status_message = f"Neo4j schema {current}/{total}: {statement[:80]}"
