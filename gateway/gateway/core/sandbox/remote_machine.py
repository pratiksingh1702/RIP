"""Remote Machine Connector — Connect to user's own machine via RIP."""
from __future__ import annotations
import logging
from typing import Any
import httpx
from gateway.config import settings

logger = logging.getLogger(__name__)

class RemoteMachineConnector:
    def __init__(self):
        self._connections: dict[str, dict[str, Any]] = {}

    async def connect(self, user_id: str, machine_url: str, api_key: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{machine_url}/health", headers={"Authorization": f"Bearer {api_key}"})
                resp.raise_for_status()
            conn_id = f"remote-{user_id}"
            self._connections[conn_id] = {"user_id": user_id, "machine_url": machine_url, "api_key": api_key, "status": "connected"}
            logger.info("Remote machine connected: %s for user %s", machine_url, user_id)
            return {"connection_id": conn_id, "status": "connected", "machine_url": machine_url}
        except Exception as e:
            logger.error("Remote connection failed: %s", e)
            raise RuntimeError(f"Could not connect to remote machine: {e}") from e

    async def disconnect(self, connection_id: str) -> bool:
        if connection_id in self._connections:
            del self._connections[connection_id]
            return True
        return False

    async def execute_remote(self, connection_id: str, command: str, project_id: str) -> tuple[int, str]:
        conn = self._connections.get(connection_id)
        if not conn: return -1, "Not connected to remote machine"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{conn['machine_url']}/gateway/api/sandbox/exec", json={"command": command, "project_id": project_id}, headers={"Authorization": f"Bearer {conn['api_key']}"})
                resp.raise_for_status()
                data = resp.json()
                return data.get("exit_code", -1), data.get("output", "")
        except Exception as e: return -1, f"Remote execution failed: {e}"

    def get_connection(self, user_id: str) -> dict[str, Any] | None:
        return self._connections.get(f"remote-{user_id}")

    def is_connected(self, user_id: str) -> bool:
        return f"remote-{user_id}" in self._connections

_remote_connector: RemoteMachineConnector | None = None
def get_remote_connector() -> RemoteMachineConnector:
    global _remote_connector
    if _remote_connector is None: _remote_connector = RemoteMachineConnector()
    return _remote_connector
