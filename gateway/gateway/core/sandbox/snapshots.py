"""Snapshot Manager — Save and restore sandbox state."""
from __future__ import annotations
import logging
from datetime import UTC, datetime
from uuid import uuid4
from gateway.core.sandbox.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)

class SnapshotManager:
    def __init__(self):
        self._orchestrator = get_orchestrator()

    async def create_snapshot(self, sandbox_id: str, label: str = "") -> dict:
        snapshot_id = f"snap-{uuid4().hex[:12]}"
        try:
            container = self._orchestrator.client.containers.get(sandbox_id)
            container.commit(repository="rip-sandbox-snapshots", tag=snapshot_id)
            logger.info("Snapshot created: %s for sandbox %s", snapshot_id, sandbox_id)
            return {"snapshot_id": snapshot_id, "sandbox_id": sandbox_id, "label": label or f"Snapshot {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}", "created_at": datetime.now(UTC).isoformat()}
        except Exception as e:
            logger.error("Snapshot failed: %s", e)
            raise RuntimeError(f"Snapshot failed: {e}") from e

    async def restore_snapshot(self, sandbox_id: str, snapshot_id: str) -> bool:
        try:
            container = self._orchestrator.client.containers.get(sandbox_id)
            container.stop(timeout=10)
            container.remove(force=True)
            self._orchestrator.client.containers.run(image=f"rip-sandbox-snapshots:{snapshot_id}", name=sandbox_id, detach=True, network=self._orchestrator.SANDBOX_NETWORK, labels={"rip-sandbox": "true"}, mem_limit="2g", nano_cpus=2_000_000_000, working_dir="/workspace", tty=True, stdin_open=True)
            logger.info("Snapshot restored: %s -> %s", snapshot_id, sandbox_id)
            return True
        except Exception as e:
            logger.error("Restore failed: %s", e)
            return False

    async def list_snapshots(self, sandbox_id: str) -> list[dict]:
        try:
            images = self._orchestrator.client.images.list(name="rip-sandbox-snapshots")
            return [{"snapshot_id": tag, "created": img.attrs.get("Created", "")} for img in images for tag in img.tags if tag.startswith("rip-sandbox-snapshots:snap-")]
        except Exception: return []

    async def delete_snapshot(self, snapshot_id: str) -> bool:
        try:
            self._orchestrator.client.images.remove(image=f"rip-sandbox-snapshots:{snapshot_id}", force=True)
            return True
        except Exception: return False

_snapshot_manager: SnapshotManager | None = None
def get_snapshot_manager() -> SnapshotManager:
    global _snapshot_manager
    if _snapshot_manager is None: _snapshot_manager = SnapshotManager()
    return _snapshot_manager
