"""Notification blocks for alerts and messages."""

from __future__ import annotations

from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.events import get_event_bus


class NotifyPushBlock(Block):
    id = "notify.push"
    kind = BlockKind.NOTIFICATION
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "message": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high"], "default": "normal"},
        },
        "required": ["title", "message"],
    }
    output_schema = {"type": "object", "properties": {"sent": {"type": "boolean"}}}
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            bus = get_event_bus()
            await bus.publish(
                "notification.push",
                workflow_run_id=ctx.workflow_run_id,
                payload={
                    "title": str(inputs["title"]),
                    "message": str(inputs["message"]),
                    "priority": str(inputs.get("priority", "normal")),
                },
            )
            return BlockResult(ok=True, output={"sent": True})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Push Notification", "description": "Send a push notification", "category": "Notifications", "display_icon": "📱", "display_color": "#EC4899", "input_schema": self.input_schema, "output_schema": self.output_schema}


class NotifySlackBlock(Block):
    id = "notify.slack"
    kind = BlockKind.NOTIFICATION
    input_schema = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Slack channel name"},
            "message": {"type": "string"},
            "blocks": {"type": "array", "description": "Slack Block Kit JSON"},
        },
        "required": ["channel", "message"],
    }
    output_schema = {"type": "object", "properties": {"sent": {"type": "boolean"}, "channel": {"type": "string"}}}
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            bus = get_event_bus()
            await bus.publish(
                "notification.slack",
                workflow_run_id=ctx.workflow_run_id,
                payload={
                    "channel": str(inputs["channel"]),
                    "message": str(inputs["message"]),
                    "blocks": inputs.get("blocks"),
                },
            )
            return BlockResult(ok=True, output={"sent": True, "channel": str(inputs["channel"])})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Slack Message", "description": "Send a Slack message", "category": "Notifications", "display_icon": "💬", "display_color": "#EC4899", "input_schema": self.input_schema, "output_schema": self.output_schema}


class NotifyWebhookBlock(Block):
    id = "notify.webhook"
    kind = BlockKind.NOTIFICATION
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "payload": {"type": "object"},
            "headers": {"type": "object"},
        },
        "required": ["url", "payload"],
    }
    output_schema = {"type": "object", "properties": {"status_code": {"type": "integer"}, "sent": {"type": "boolean"}}}
    config_schema = {}
    requires_capabilities = ["NETWORK"]

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            import httpx
        except ImportError:
            return BlockResult(ok=False, error="httpx not installed")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    str(inputs["url"]),
                    json=inputs["payload"],
                    headers=inputs.get("headers", {}),
                )
            return BlockResult(ok=resp.is_success, output={"status_code": resp.status_code, "sent": resp.is_success})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Webhook", "description": "Call a webhook URL", "category": "Notifications", "display_icon": "🔔", "display_color": "#EC4899", "input_schema": self.input_schema, "output_schema": self.output_schema}
