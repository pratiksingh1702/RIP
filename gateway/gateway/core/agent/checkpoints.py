"""Checkpoints: Temporary Git task branch checkpoint manager for Main Agent step executions."""

from __future__ import annotations

import asyncio
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages Git step checkpoints on temporary task branches (rip/task-<task_id>)."""

    async def init_task_branch(self, task_id: str, repo_root: Path) -> str:
        """Create and checkout temporary branch rip/task-<task_id>."""
        branch_name = f"rip/task-{task_id[:8]}"
        try:
            # Check current branch
            stdout, _ = await self._run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
            original_branch = stdout.strip() or "main"
            
            # Create temporary branch from current HEAD
            await self._run_git(repo_root, ["checkout", "-b", branch_name])
            logger.info(f"Created temporary task checkpoint branch: {branch_name} (from {original_branch})")
            return branch_name
        except Exception as e:
            logger.warning(f"Failed to create task branch {branch_name}: {e}. Proceeding on active branch.")
            return "active"

    async def create_step_checkpoint(
        self,
        task_id: str,
        step_id: str,
        step_title: str,
        repo_root: Path,
    ) -> str | None:
        """Stage changes and commit checkpoint for step."""
        try:
            # Check if there are modified files
            stdout, _ = await self._run_git(repo_root, ["status", "--porcelain"])
            if not stdout.strip():
                return None  # No changes to commit
            
            await self._run_git(repo_root, ["add", "-A"])
            commit_msg = f"RIP Checkpoint: Step [{step_id}] {step_title}"
            await self._run_git(repo_root, ["commit", "-m", commit_msg])
            
            stdout, _ = await self._run_git(repo_root, ["rev-parse", "HEAD"])
            commit_hash = stdout.strip()
            logger.info(f"Created step checkpoint {commit_hash[:7]} for step {step_id}")
            return commit_hash
        except Exception as e:
            logger.error(f"Error creating step checkpoint for {step_id}: {e}")
            return None

    async def rollback_step(self, task_id: str, commit_hash: str, repo_root: Path) -> bool:
        """Revert changes back to specific step commit."""
        try:
            await self._run_git(repo_root, ["reset", "--hard", commit_hash])
            logger.info(f"Rolled back task {task_id} state to commit {commit_hash[:7]}")
            return True
        except Exception as e:
            logger.error(f"Failed to rollback step for commit {commit_hash}: {e}")
            return False

    async def finalize_task_branch(
        self,
        task_id: str,
        original_branch: str,
        merge: bool,
        repo_root: Path,
    ) -> bool:
        """Merge temporary task branch into original branch or delete branch on abort."""
        branch_name = f"rip/task-{task_id[:8]}"
        try:
            if merge:
                await self._run_git(repo_root, ["checkout", original_branch])
                await self._run_git(repo_root, ["merge", "--no-ff", branch_name, "-m", f"Merge task {task_id} changes"])
                await self._run_git(repo_root, ["branch", "-d", branch_name])
                logger.info(f"Successfully merged task branch {branch_name} into {original_branch}")
            else:
                await self._run_git(repo_root, ["checkout", original_branch])
                await self._run_git(repo_root, ["branch", "-D", branch_name])
                logger.info(f"Discarded task branch {branch_name}")
            return True
        except Exception as e:
            logger.error(f"Error finalizing task branch {branch_name}: {e}")
            return False

    async def _run_git(self, cwd: Path, args: list[str]) -> tuple[str, str]:
        cmd = ["git"] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{stderr.decode()}")
        return stdout.decode(), stderr.decode()


# Global singleton instance
checkpoint_manager = CheckpointManager()
