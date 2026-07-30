"""Git clone service for indexing remote repositories."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from core.graph.client import Neo4jClient
from core.indexer.pipeline import index_repository_with_resources
from core.projects import project_id_for_root, upsert_project
from core.storage.database import async_session_factory
from server.config import default_config_toml, get_settings

logger = logging.getLogger(__name__)


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
    folder_name: str
    subdirectory: str | None
    status: CloneStatus
    project_id: str | None = None
    clone_path: str | None = None
    index_path: str | None = None
    error: str | None = None
    files_indexed: int = 0
    entities_found: int = 0
    logs: list[str] = field(default_factory=list)

    def add_log(self, msg: str):
        import datetime
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{now_str}] {msg}"
        self.logs.append(log_entry)
        self.progress_message = msg


class GitCloneService:
    """
    Clones a git repository to an explicit isolated folder and indexes that folder.
    The graph and vectors persist in Neo4j and Qdrant with stable project ids.
    """

    # Store active jobs in memory
    _jobs: dict[str, CloneJob] = {}

    async def start_clone_and_index(
        self,
        git_url: str,
        project_name: str,
        folder_name: str,
        subdirectory: str | None = None,
        branch: str = "main",
        keep_clone: bool = True,
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
            folder_name=folder_name,
            subdirectory=subdirectory,
            status=CloneStatus.PENDING,
        )
        self._jobs[job_id] = job

        # Run in background so we can return immediately
        asyncio.create_task(
            self._clone_and_index(job, keep_clone)
        )

        return job_id

    async def run_clone_and_index(
        self,
        git_url: str,
        project_name: str,
        folder_name: str,
        subdirectory: str | None = None,
        branch: str = "main",
        keep_clone: bool = True,
    ) -> CloneJob:
        """Run clone-and-index inline for CLI callers."""
        job_id = str(uuid.uuid4())
        job = CloneJob(
            job_id=job_id,
            git_url=git_url,
            project_name=project_name,
            branch=branch,
            folder_name=folder_name,
            subdirectory=subdirectory,
            status=CloneStatus.PENDING,
        )
        self._jobs[job_id] = job
        await self._clone_and_index(job, keep_clone)
        return job

    async def _clone_and_index(self, job: CloneJob, keep_clone: bool):
        """Background task: clone → index → cleanup."""

        clone_path = None

        try:
            # Step 1: Clone
            job.status = CloneStatus.CLONING
            clone_path = self._resolve_clone_path(job.folder_name)
            job.clone_path = str(clone_path)
            job.add_log("╭─────────────────────────────────────────────── 🔍 Repository Indexing ───────────────────────────────────────────────╮")
            job.add_log(f"│  📂 Project: {job.project_name}")
            job.add_log(f"│  🔗 Target URL: {job.git_url} (branch: {job.branch})")
            job.add_log("│  ⚡ Step 1/4: Cloning git repository to local workspace...")

            if clone_path.exists():
                _force_rmtree(clone_path)
            clone_path.parent.mkdir(parents=True, exist_ok=True)

            # Use git subprocess — asyncio-safe
            result = await asyncio.to_thread(
                _run_git_clone,
                git_url=job.git_url,
                branch=job.branch,
                clone_path=clone_path,
            )

            if result.returncode != 0:
                stderr_text = result.stderr.strip()
                stdout_text = result.stdout.strip()
                detail = stderr_text or stdout_text or "git produced no output"
                job.add_log(f"❌ Git clone failed with exit code {result.returncode}")
                job.add_log("╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯")
                raise RuntimeError(f"Git clone failed with exit code {result.returncode}: {detail[:500]}")

            index_path = self._resolve_index_path(clone_path, job.subdirectory)
            job.index_path = str(index_path)
            job.add_log(f"│  ✅ Clone complete! Workspace path: {index_path.name}")
            job.add_log("│")

            # Step 2: Initialize RIP project
            job.status = CloneStatus.INDEXING
            job.add_log("│  ⚡ Step 2/4: Initializing Tree-Sitter AST parser & Neo4j Knowledge Graph...")

            settings = get_settings()

            project_id = project_id_for_root(index_path)
            job.project_id = project_id
            self._write_project_config(index_path, job.project_name)

            # Create IndexProgress to track exact live pipeline state (matching CLI repo index)
            from core.indexer.pipeline import IndexProgress
            progress = IndexProgress()

            # Start real-time background monitor loop for CLI-style telemetry
            async def _monitor_progress():
                last_stage = None
                last_file = None
                last_parsed_count = -1
                while job.status == CloneStatus.INDEXING:
                    try:
                        job.files_indexed = progress.files_parsed
                        job.entities_found = progress.entities_extracted
                        stage = progress.current_stage or "Indexing"

                        # Generate detailed progress_message matching CLI display
                        if progress.files_scanned > 0:
                            pct = min(progress.files_parsed / max(progress.files_scanned, 1) * 100, 100)
                            job.progress_message = (
                                f"⚡ [{stage}] Parsed {progress.files_parsed}/{progress.files_scanned} files ({pct:.0f}%) | "
                                f"Entities: {progress.entities_extracted:,} | Neo4j: {progress.neo4j_entities_written:,} | "
                                f"Qdrant: {progress.embeddings_generated:,}"
                            )
                        else:
                            job.progress_message = f"⚡ [{stage}] Processing pipeline..."

                        # Log stage transitions & parsing milestones
                        if stage != last_stage:
                            last_stage = stage
                            job.add_log(f"│  ⚡ Stage: {stage} ...")

                        if progress.current_parsing_file and progress.current_parsing_file != last_file:
                            last_file = progress.current_parsing_file
                            try:
                                fname = Path(progress.current_parsing_file).name
                            except Exception:
                                fname = str(progress.current_parsing_file)
                            job.add_log(f"│  📝 Parsing: {fname} (Size: {progress.current_file_size / 1024:.1f}KB)")

                        if progress.files_parsed > 0 and progress.files_parsed != last_parsed_count and progress.files_parsed % 15 == 0:
                            last_parsed_count = progress.files_parsed
                            job.add_log(
                                f"│  📊 Progress: {progress.files_parsed}/{progress.files_scanned} files | "
                                f"Entities: {progress.entities_extracted:,} | Neo4j: {progress.neo4j_entities_written:,} | "
                                f"Embeds (Qdrant): {progress.embeddings_generated:,}"
                            )

                    except Exception as err:
                        logger.warning("Error in progress monitor: %s", err)

                    await asyncio.sleep(0.25)

            monitor_task = asyncio.create_task(_monitor_progress())

            # Run the existing indexing pipeline with live progress object
            client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
            try:
                summary = await index_repository_with_resources(
                    repo_path=index_path,
                    client=client,
                    progress=progress,
                    project_id=project_id,
                    project_name=job.project_name,
                )
            finally:
                monitor_task.cancel()
                await client.close()

            job.files_indexed = summary.indexed_files
            job.entities_found = summary.total_entities

            job.add_log(f"│  ✅ Parsed {summary.indexed_files} files across languages: {', '.join(summary.languages_detected) if summary.languages_detected else 'Code'}")
            job.add_log(f"│  ✅ Extracted {summary.total_entities} AST entities & dependency relationships into Neo4j graph")
            job.add_log("│")
            job.add_log("│  ⚡ Step 3/4: Generating vector embeddings & storing in Qdrant Vector Memory...")
            job.add_log(f"│  📊 Entities: {summary.total_entities} | Neo4j: {summary.total_entities} | Qdrant Vectors: {progress.embeddings_generated or summary.total_entities}")
            job.add_log("│")

            # Step 3: Persist project to PostgreSQL
            job.add_log("│  ⚡ Step 4/4: Persisting project metadata & indexing execution memory...")
            async with async_session_factory() as session:
                await upsert_project(
                    session=session,
                    project_id=project_id,
                    project_name=job.project_name,
                    root=str(index_path),
                    git_url=job.git_url,
                    branch=job.branch,
                    files_count=summary.indexed_files,
                    entities_count=summary.total_entities,
                    languages=summary.languages_detected,
                )

            # Step 4: Record Workspace Memory & Knowledge Context
            try:
                import sys
                from pathlib import Path
                gateway_dir = Path(__file__).resolve().parent.parent.parent / "gateway"
                if str(gateway_dir) not in sys.path:
                    sys.path.insert(0, str(gateway_dir))

                try:
                    from gateway.core.workspace.memory import get_workspace_memory
                    ws_mem = get_workspace_memory()
                    await ws_mem.record(
                        workspace_id=project_id,
                        project_id=project_id,
                        category="repository_index",
                        intent="initial_onboarding_index",
                        query=f"Index repository {job.project_name}",
                        summary=f"Successfully cloned and indexed {job.project_name} ({summary.indexed_files} files, {summary.total_entities} entities).",
                        result_data={
                            "git_url": job.git_url,
                            "branch": job.branch,
                            "files_indexed": summary.indexed_files,
                            "entities_found": summary.total_entities,
                            "languages": summary.languages_detected,
                        },
                        status="completed",
                        created_by="git_onboarding_pipeline",
                    )
                    job.add_log("│  ✅ Recorded event in Workspace Memory table")
                except Exception as w_err:
                    logger.warning("Could not record workspace memory event: %s", w_err)

                try:
                    from gateway.core.agent.memory import get_execution_memory
                    exec_mem = get_execution_memory()
                    exec_mem.record_result(
                        project_id=project_id,
                        file_path="REPOSITORY_ROOT",
                        success=True,
                        error=None,
                        tool_name="git_onboarding_indexer",
                    )
                    job.add_log("│  ✅ Initialized Agent Execution Memory store")
                except Exception as e_err:
                    logger.warning("Could not record execution memory: %s", e_err)

            except Exception as mem_err:
                logger.warning("Memory integration warning: %s", mem_err)

            job.status = CloneStatus.COMPLETE
            job.add_log("╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯")
            job.add_log("╭─────────────────────────────────────────────────── Index Complete ───────────────────────────────────────────────────╮")
            job.add_log(f"│ ✅ {summary.indexed_files} files indexed into Knowledge Graph")
            job.add_log(f"│ ✅ {summary.total_entities} AST entities & relationships mapped in Neo4j")
            job.add_log(f"│ ✅ {summary.total_entities} embeddings stored in Qdrant Vector Memory")
            job.add_log("╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯")

        except asyncio.CancelledError:
            job.status = CloneStatus.FAILED
            job.error = "Index job was cancelled, usually because the server reloaded or shut down"
            job.progress_message = f"Failed: {job.error}"
            logger.warning(
                "Git index job %s cancelled: git_url=%s folder=%s subdirectory=%s",
                job.job_id,
                job.git_url,
                job.folder_name,
                job.subdirectory,
            )
            raise
        except Exception as e:
            detail = _exception_detail(e)
            job.status = CloneStatus.FAILED
            job.error = detail
            job.progress_message = f"Failed: {detail}"
            logger.exception(
                "Git index job %s failed: git_url=%s folder=%s subdirectory=%s clone_path=%s index_path=%s",
                job.job_id,
                job.git_url,
                job.folder_name,
                job.subdirectory,
                job.clone_path,
                job.index_path,
            )

        finally:
            # Step 4: Optional clean up. Keeping clones is preferred for project isolation.
            if clone_path and clone_path.exists() and not keep_clone:
                shutil.rmtree(clone_path, ignore_errors=True)

    def get_job(self, job_id: str) -> CloneJob | None:
        """Get a specific job by ID."""
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> list[CloneJob]:
        """Get all jobs."""
        return list(self._jobs.values())

    def _resolve_clone_path(self, folder_name: str) -> Path:
        clean = self._sanitize_folder_name(folder_name)
        settings = get_settings()
        root = Path(settings.git_repos_root).expanduser()
        if not root.is_absolute():
            root = Path.cwd() / root
        root = root.resolve()
        clone_path = (root / clean).resolve()
        if root != clone_path and root not in clone_path.parents:
            raise RuntimeError("Clone folder must stay inside the configured git repositories root")
        return clone_path

    def _sanitize_folder_name(self, folder_name: str) -> str:
        candidate = folder_name.strip()
        if not candidate:
            raise RuntimeError("folder_name is required")
        if "/" in candidate or "\\" in candidate:
            raise RuntimeError("folder_name must be a single folder name, not a path")
        clean = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip(".-_")
        if not clean or clean in {".", ".."}:
            raise RuntimeError("folder_name must contain letters or numbers")
        return clean[:80]

    def _resolve_index_path(self, clone_path: Path, subdirectory: str | None) -> Path:
        if subdirectory is None or not subdirectory.strip():
            return clone_path
        candidate = subdirectory.strip().replace("\\", "/").strip("/")
        if not candidate or candidate in {".", ".."}:
            return clone_path
        parts = [part for part in candidate.split("/") if part and part not in {"."}]
        if any(part == ".." for part in parts):
            raise RuntimeError("subdirectory must stay inside the cloned repository")
        index_path = clone_path.joinpath(*parts).resolve()
        if clone_path != index_path and clone_path not in index_path.parents:
            raise RuntimeError("subdirectory must stay inside the cloned repository")
        if not index_path.exists() or not index_path.is_dir():
            raise RuntimeError(f"Index subdirectory does not exist after clone: {candidate}")
        return index_path

    def _write_project_config(self, clone_path: Path, project_name: str) -> None:
        config_dir = clone_path / ".repo-intel"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.toml").write_text(
            default_config_toml(clone_path, project_name=project_name),
            encoding="utf-8",
        )


# Global singleton
_clone_service = GitCloneService()


def get_clone_service() -> GitCloneService:
    """Get the global clone service singleton."""
    return _clone_service


def _exception_detail(exc: Exception) -> str:
    text = str(exc).strip()
    if text:
        return text
    representation = repr(exc).strip()
    if representation and representation != f"{type(exc).__name__}()":
        return representation
    return type(exc).__name__


def _force_rmtree(path: Path) -> None:
    """Force delete a directory tree handling Windows read-only permissions and locked files."""
    import os
    import stat

    def handle_remove_readonly(func, p, exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    try:
        if path.exists():
            shutil.rmtree(path, onerror=handle_remove_readonly)
    except Exception:
        pass

    if path.exists():
        try:
            temp_name = path.parent / f"_trash_{path.name}_{uuid.uuid4().hex[:6]}"
            path.rename(temp_name)
            shutil.rmtree(temp_name, ignore_errors=True)
        except Exception:
            pass


def _run_git_clone(git_url: str, branch: str, clone_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "clone",
            "--branch",
            branch,
            "--depth",
            "1",
            "--single-branch",
            git_url,
            str(clone_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
