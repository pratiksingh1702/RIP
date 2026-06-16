"""Git history ingestion."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import git

logger = logging.getLogger(__name__)


@dataclass
class GitCommit:
    hash: str
    message: str
    author_name: str
    author_email: str
    timestamp: datetime
    files_modified: list[str] = field(default_factory=list)


@dataclass
class FileOwnership:
    developer_name: str
    developer_email: str
    line_count: int
    percentage: float


class GitIngestor:
    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path).resolve()
        self._repo: git.Repo | None = None
        try:
            self._repo = git.Repo(self.repo_path, search_parent_directories=True)
        except Exception as e:
            logger.warning("Path %s is not a valid git repository: %s", repo_path, e)

    @property
    def is_git_repo(self) -> bool:
        return self._repo is not None

    def get_commits(self, limit: int = 100) -> list[GitCommit]:
        if not self._repo:
            return []
        commits = []
        try:
            for commit in self._repo.iter_commits(max_count=limit):
                # get modified files
                files = list(commit.stats.files.keys())
                commits.append(
                    GitCommit(
                        hash=commit.hexsha,
                        message=commit.message.strip() if isinstance(commit.message, str) else "",
                        author_name=commit.author.name or "Unknown",
                        author_email=commit.author.email or "unknown@example.com",
                        timestamp=datetime.fromtimestamp(commit.committed_date),
                        files_modified=files,
                    )
                )
        except Exception as e:
            logger.error("Error retrieving git commits: %s", e)
        return commits

    def get_file_ownership(self, file_path: str | Path) -> list[FileOwnership]:
        if not self._repo:
            return []
        full_path = Path(file_path).resolve()
        if not full_path.exists():
            return []
        
        # Make path relative to repo root
        try:
            rel_path = full_path.relative_to(self._repo.working_dir)
        except ValueError:
            rel_path = Path(file_path)

        ownership_map: dict[str, tuple[str, int]] = {}  # email -> (name, line_count)
        total_lines = 0

        try:
            # Run git blame
            for commit, lines in self._repo.blame(None, str(rel_path.as_posix())):
                line_count = len(lines)
                total_lines += line_count
                author = commit.author
                email = author.email or "unknown@example.com"
                name = author.name or "Unknown"
                if email in ownership_map:
                    ownership_map[email] = (name, ownership_map[email][1] + line_count)
                else:
                    ownership_map[email] = (name, line_count)
        except Exception as e:
            logger.warning("Could not run git blame on %s: %s", file_path, e)
            return []

        results = []
        for email, (name, count) in ownership_map.items():
            percentage = (count / total_lines) if total_lines > 0 else 0.0
            results.append(
                FileOwnership(
                    developer_name=name,
                    developer_email=email,
                    line_count=count,
                    percentage=percentage,
                )
            )
        
        # Sort by line count descending
        results.sort(key=lambda x: x.line_count, reverse=True)
        return results

    def get_churn_map(self) -> dict[str, int]:
        """Returns map of file_path (relative to repo root) -> modification count."""
        if not self._repo:
            return {}
        churn: dict[str, int] = {}
        try:
            # We can traverse commits to count file changes
            for commit in self._repo.iter_commits():
                for f in commit.stats.files.keys():
                    churn[f] = churn.get(f, 0) + 1
        except Exception as e:
            logger.error("Error calculating file churn: %s", e)
        return churn
