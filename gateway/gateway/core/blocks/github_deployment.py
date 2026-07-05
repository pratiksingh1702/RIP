"""GitHub deployment blocks."""

from __future__ import annotations

from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.sources.github import GitHubSource
from gateway.core.workflow.policies import workflow_action_allowed


class _GitHubWriteBlock(Block):
    query_type = ""
    action = ""
    name = ""
    description = ""
    input_schema: dict[str, Any] = {"type": "object"}
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "metadata": {"type": "object"},
        },
    }
    config_schema = {"type": "object"}
    kind = BlockKind.DEPLOYMENT
    requires_capabilities = ["github:write"]

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        source = GitHubSource(enabled=True)
        await source._load_runtime_config()
        repo = str(inputs.get("repo") or config.get("repo") or source.repo or "").strip()
        if repo:
            source.repo = repo
        allowed, reason = await workflow_action_allowed(self.action, source.repo)
        if not allowed:
            return BlockResult(ok=False, error=reason)
        result = await source.query(self.query_type, {**config, **inputs, "project_id": ctx.project_id})
        return BlockResult(
            ok=result.success,
            output={"content": result.content, "metadata": result.metadata},
            error=result.error,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }


class GitHubCreateBranchBlock(_GitHubWriteBlock):
    id = "github.create_branch"
    query_type = "create_branch"
    action = "github.create_branch"
    name = "Create Branch"
    description = "Create a GitHub branch from the repository default branch or a selected base."
    input_schema = {
        "type": "object",
        "properties": {
            "branch": {"type": "string"},
            "base_branch": {"type": "string"},
            "repo": {"type": "string"},
        },
        "required": ["branch"],
    }


class GitHubCommitFilesBlock(_GitHubWriteBlock):
    id = "github.commit_files"
    query_type = "commit_files"
    action = "github.commit_files"
    name = "Commit Files"
    description = "Commit one or more generated file changes to a GitHub branch."
    input_schema = {
        "type": "object",
        "properties": {
            "branch": {"type": "string"},
            "message": {"type": "string"},
            "files": {"type": "array"},
            "repo": {"type": "string"},
        },
        "required": ["branch", "files"],
    }


class GitHubOpenPrBlock(_GitHubWriteBlock):
    id = "github.open_pr"
    query_type = "open_pr"
    action = "github.open_pr"
    name = "Open PR"
    description = "Open a pull request from a workflow branch."
    input_schema = {
        "type": "object",
        "properties": {
            "branch": {"type": "string"},
            "base_branch": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "repo": {"type": "string"},
        },
        "required": ["branch", "title"],
    }
