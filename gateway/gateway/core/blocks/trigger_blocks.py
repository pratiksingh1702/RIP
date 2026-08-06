"""Trigger blocks for automated workflow initiation."""

from __future__ import annotations

from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext


class TriggerCronBlock(Block):
    id = "trigger.cron"
    kind = BlockKind.TRIGGER
    input_schema = {
        "type": "object",
        "properties": {
            "schedule": {"type": "string", "description": "Cron expression, e.g. '0 2 * * 1'"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "triggered_at": {"type": "string"},
            "schedule": {"type": "string"},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "schedule": {"type": "string", "default": "0 2 * * 1"},
            "timezone": {"type": "string", "default": "UTC"},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        sched = config.get("schedule", "0 2 * * 1")
        tz = config.get("timezone", "UTC")
        return BlockResult(
            ok=True,
            output={
                "trigger_type": "cron",
                "schedule": sched,
                "timezone": tz,
                "status": "active",
            },
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Cron Schedule Trigger",
            "description": "Runs workflows on a recurring schedule without manual user intervention",
            "category": "Trigger",
            "display_icon": "⏰",
            "display_color": "#EC4899",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }


class TriggerWebhookBlock(Block):
    id = "trigger.webhook"
    kind = BlockKind.TRIGGER
    input_schema = {
        "type": "object",
        "properties": {
            "event": {"type": "string", "description": "Event name, e.g. github.pull_request.opened"},
            "payload": {"type": "object", "description": "Incoming HTTP webhook payload"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "event": {"type": "string"},
            "pr_id": {"type": "string"},
            "payload": {},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "event": {"type": "string", "default": "github.pull_request.opened"},
            "repo_filter": {"type": "string", "default": "*"},
            "secret_ref": {"type": "string"},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        evt = config.get("event", "webhook_received")
        payload = inputs.get("payload", {})
        return BlockResult(
            ok=True,
            output={
                "trigger_type": "webhook",
                "event": evt,
                "payload": payload,
            },
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Webhook Trigger",
            "description": "Fires automatically when GitHub PRs or external HTTP webhooks are received",
            "category": "Trigger",
            "display_icon": "🪝",
            "display_color": "#EC4899",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }


class TriggerFileWatchBlock(Block):
    id = "trigger.file_watch"
    kind = BlockKind.TRIGGER
    input_schema = {
        "type": "object",
        "properties": {
            "changed_files": {"type": "array"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "changed_files": {"type": "array"},
            "event": {"type": "string"},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "path_glob": {"type": "string", "default": "src/**/*.py"},
            "event": {"type": "string", "default": "on_change"},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        files = inputs.get("changed_files", [])
        glob = config.get("path_glob", "src/**/*")
        return BlockResult(
            ok=True,
            output={
                "trigger_type": "file_watch",
                "path_glob": glob,
                "changed_files": files,
            },
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "File Watcher Trigger",
            "description": "Fires automatically when files matching a glob pattern are modified or saved",
            "category": "Trigger",
            "display_icon": "👁️",
            "display_color": "#EC4899",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }
