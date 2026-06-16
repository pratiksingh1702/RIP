"""Index worker."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from core.graph.client import Neo4jClient
from core.indexer.incremental import incremental_index
from core.storage.database import async_session_factory
from core.storage.models.index_state import IndexState
from server.config import get_settings

logger = logging.getLogger(__name__)


class IndexWorker:
    """Background worker for repository indexing tasks."""

    def __init__(self):
        self.queue: asyncio.Queue[Path] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._is_running = False

    def start(self) -> None:
        """Start the background worker task."""
        if not self._is_running:
            self._is_running = True
            self._worker_task = asyncio.create_task(self._loop())
            logger.info("IndexWorker background loop started.")

    async def stop(self) -> None:
        """Stop the background worker."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("IndexWorker background loop stopped.")

    def submit_job(self, repo_path: Path) -> None:
        """Submit a repository path to be indexed."""
        self.queue.put_nowait(repo_path)
        logger.info(f"Submitted repository to index queue: {repo_path}")

    async def _loop(self) -> None:
        while self._is_running:
            try:
                repo_path = await self.queue.get()
            except asyncio.CancelledError:
                break

            try:
                logger.info(f"IndexWorker processing repository: {repo_path}")
                await self._process_job(repo_path)
            except Exception as e:
                logger.error(f"Error processing index job for {repo_path}: {e}", exc_info=True)
            finally:
                self.queue.task_done()

    async def _process_job(self, repo_path: Path) -> None:
        settings = get_settings()
        neo_client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
        await neo_client.connect()

        async with async_session_factory() as db_session:
            stmt = select(IndexState).where(IndexState.repo_path == str(repo_path))
            res = await db_session.execute(stmt)
            state = res.scalar_one_or_none()
            if not state:
                state = IndexState(repo_path=str(repo_path))
                db_session.add(state)
            state.status = "indexing"
            state.error_message = None
            await db_session.commit()

            try:
                results = await incremental_index(repo_path, neo_client, db_session)
                logger.info(f"Incremental indexing completed: {results}")
                state.status = "completed"
            except Exception as e:
                logger.error(f"Failed incremental index for {repo_path}: {e}")
                state.status = "failed"
                state.error_message = str(e)
            finally:
                await db_session.commit()
                await neo_client.close()


worker = IndexWorker()
