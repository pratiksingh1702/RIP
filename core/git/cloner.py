"""Git clone service for indexing remote repositories."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from core.graph.client import Neo4jClient
from core.indexer.pipeline import index_repository_with_resources
from core.projects import upsert_project
from core.storage.database import async_session_factory
from server.config import get_settings


class CloneStatus(str, Enum):
    """Status of a git clone job."""
    PENDING = "pending"
    CLONING = "cloning"
    INDEXING = "indexing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class CloneJob:
    """Data class representing a git clone/index job."""
    job_id: str
    git_url: str
    project_name: str
    branch: str
    status: CloneStatus
    project_id: str | None = None
    error: str | None = None
    progress_message: str = ""
    files_indexed: int = 0
    entities_found: int = 0


class GitCloneService:
    """
    Clones a git repository to a temp folder, runs the RIP indexing pipeline, then removes the clone.
    The graph and vectors persist in Neo4j and Qdrant.
    """

    # Store active jobs in memory
    _jobs: dict[str, CloneJob] = {}

    async def start_clone_and_index(
        self,
        git_url: str,
        project_name: str,
        branch: str = "main",
        keep_clone: bool = False,
    ) -> str:
        """
        Start a clone-and-index job.
        Returns job_id immediately.
        Job runs in the background.
        """
        job_id = str(uuid.uuid4())

        job = CloneJob(
            job_id=job_id,
            git_url=git_url,
            project_name=project_name,
            branch=branch,
            status=CloneStatus.PENDING,
        )
        self._jobs[job_id] = job

        # Run in background so we can return immediately
        asyncio.create_task(
            self._clone_and_index(job, keep_clone)
        )

        return job_id

    async def _clone_and_index(self, job: CloneJob, keep_clone: bool):
        """Background task: clone → index → cleanup."""

        clone_path = None

        try:
            # Step 1: Clone
            job.status = CloneStatus.CLONING
            job.progress_message = f"Cloning {job.git_url}..."

            clone_path = Path(tempfile.mkdtemp()) / f"rip_{job.job_id}"

            # Use git subprocess — asyncio-safe
            result = await asyncio.create_subprocess_exec(
                "git", "clone",
                "--branch", job.branch,
                "--depth", "1",  # Shallow clone for speed
                "--single-branch",
                str(job.git_url),
                str(clone_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                raise RuntimeError(
                    f"Git clone failed: {stderr.decode()[:500]}"
                )

            job.progress_message = "Clone complete. Starting indexing..."

            # Step 2: Initialize RIP project
            job.status = CloneStatus.INDEXING

            settings = get_settings()

            # Use project_name as project identifier
            project_id = f"{job.project_name.lower().replace(' ', '-')}-{job.job_id[:8]}"
            job.project_id = project_id

            # Run the existing indexing pipeline
            client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
            try:
                summary = await index_repository_with_resources(
                    repo_path=clone_path,
                    client=client,
                    project_id=project_id,
                    project_name=job.project_name,
                )
            finally:
                await client.close()

            # Step 3: Persist project to PostgreSQL
            async with async_session_factory() as session:
                await upsert_project(
                    session=session,
                    project_id=project_id,
                    project_name=job.project_name,
                    git_url=job.git_url,
                    branch=job.branch,
                    files_count=summary.indexed_files,
                    entities_count=summary.total_entities,
                    languages=summary.languages_detected,
                )

            job.files_indexed = summary.indexed_files
            job.entities_found = summary.total_entities
            job.status = CloneStatus.COMPLETE
            job.progress_message = (
                f"Indexed {summary.indexed_files} files, {summary.total_entities} entities"
            )

        except Exception as e:
            job.status = CloneStatus.FAILED
            job.error = str(e)
            job.progress_message = f"Failed: {e}"

        finally:
            # Step 3: Clean up clone (source files no longer needed)
            if clone_path and clone_path.exists() and not keep_clone:
                shutil.rmtree(clone_path, ignore_errors=True)

    def get_job(self, job_id: str) -> CloneJob | None:
        """Get a specific job by ID."""
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> list[CloneJob]:
        """Get all jobs."""
        return list(self._jobs.values())


# Global singleton
_clone_service = GitCloneService()


def get_clone_service() -> GitCloneService:
    """Get the global clone service singleton."""
    return _clone_service
