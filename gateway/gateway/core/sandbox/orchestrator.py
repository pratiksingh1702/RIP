"""Sandbox Orchestrator — Docker container lifecycle management."""
from __future__ import annotations
import asyncio, io, logging, os, tarfile
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from gateway.config import settings

logger = logging.getLogger(__name__)

class SandboxOrchestrator:
    SANDBOX_NETWORK = "rip-sandbox-net"
    SANDBOX_LABEL = "rip-sandbox"
    IDLE_TIMEOUT_SECONDS = 7200
    STREAM_AGENT_PORT = 7000
    STREAM_AGENT_CONTAINER_PATH = "/opt/stream_agent.py"
    _AGENT_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "stream_agent.py")

    def __init__(self):
        self._client = None
        self._ready = False

    @property
    def client(self):
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env()
                self._ready = True
            except Exception as e:
                logger.error("Docker not available: %s", e)
                self._ready = False
                raise RuntimeError("Docker is required for Project Sandbox. Install with: pip install docker") from e
        return self._client

    @property
    def is_ready(self) -> bool:
        try:
            self.client
            return True
        except Exception:
            return False

    async def create_sandbox(self, project_id: str, user_id: str, environment: str = "python", custom_config: dict[str, Any] | None = None) -> dict[str, Any]:
        sandbox_id = f"sandbox-{project_id[:8]}-{uuid4().hex[:8]}"
        try:
            self._ensure_network()
            image = self._resolve_image(environment)
            container = self.client.containers.run(
                image=image, name=sandbox_id, detach=True, network=self.SANDBOX_NETWORK,
                ports={f"{self.STREAM_AGENT_PORT}/tcp": ("127.0.0.1", None)},
                labels={self.SANDBOX_LABEL: "true", "project_id": project_id, "user_id": user_id, "environment": environment, "created_at": datetime.now(UTC).isoformat()},
                mem_limit="2g", nano_cpus=2_000_000_000, memswap_limit="3g",
                environment={"PROJECT_ID": project_id, "USER_ID": user_id, "RIP_SANDBOX": "true"},
                working_dir="/workspace", tty=True, stdin_open=True,
            )
            container.reload()
            try:
                self._deploy_stream_agent(container)
            except Exception as e:
                logger.warning("Failed to deploy stream agent: %s", e)
            logger.info("Sandbox created: %s (project=%s, user=%s)", sandbox_id, project_id, user_id)
            return {"sandbox_id": sandbox_id, "project_id": project_id, "user_id": user_id, "environment": environment, "status": container.status, "image": image, "created_at": datetime.now(UTC).isoformat()}
        except Exception as e:
            logger.error("Failed to create sandbox: %s", e)
            raise RuntimeError(f"Failed to create sandbox: {e}") from e

    async def destroy_sandbox(self, sandbox_id: str) -> bool:
        try:
            container = self.client.containers.get(sandbox_id)
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info("Sandbox destroyed: %s", sandbox_id)
            return True
        except Exception:
            return False

    async def get_sandbox_status(self, sandbox_id: str) -> dict[str, Any] | None:
        try:
            container = self.client.containers.get(sandbox_id)
            container.reload()
            stats = container.stats(stream=False)
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0
            mem_used = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 2_000_000_000)
            return {"sandbox_id": sandbox_id, "status": container.status, "cpu_percent": round(cpu_percent, 1), "memory_used_bytes": mem_used, "memory_limit_bytes": mem_limit, "memory_percent": round((mem_used / mem_limit) * 100, 1) if mem_limit > 0 else 0}
        except Exception:
            return None

    async def list_sandboxes(self, project_id: str | None = None, user_id: str | None = None) -> list[dict[str, Any]]:
        try:
            containers = self.client.containers.list(all=True, filters={"label": f"{self.SANDBOX_LABEL}=true"})
            result = []
            for c in containers:
                labels = c.labels
                if project_id and labels.get("project_id") != project_id: continue
                if user_id and labels.get("user_id") != user_id: continue
                result.append({"sandbox_id": c.name, "project_id": labels.get("project_id", ""), "user_id": labels.get("user_id", ""), "environment": labels.get("environment", ""), "status": c.status, "created_at": labels.get("created_at", "")})
            return result
        except Exception:
            return []

    async def stop_sandbox(self, sandbox_id: str) -> bool:
        try: self.client.containers.get(sandbox_id).stop(timeout=10); return True
        except Exception: return False

    async def start_sandbox(self, sandbox_id: str) -> bool:
        try: self.client.containers.get(sandbox_id).start(); return True
        except Exception: return False

    def exec_command(self, sandbox_id: str, command: str, workdir: str = "/workspace", timeout: int = 60) -> tuple[int, str]:
        try:
            container = self.client.containers.get(sandbox_id)
            exit_code, output = container.exec_run(cmd=["/bin/bash", "-c", command], workdir=workdir, stdout=True, stderr=True, tty=True)
            return exit_code, output.decode("utf-8", errors="replace")
        except Exception as e:
            return -1, str(e)

    def _deploy_stream_agent(self, container) -> None:
        """Copy stream_agent.py into the container and launch it in the background."""
        with open(self._AGENT_SCRIPT_PATH, "rb") as f:
            agent_src = f.read()
        tarstream = io.BytesIO()
        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            info = tarfile.TarInfo(name="stream_agent.py")
            info.size = len(agent_src)
            tar.addfile(info, io.BytesIO(agent_src))
        tarstream.seek(0)
        container.put_archive("/opt", tarstream)
        container.exec_run(
            cmd=["/bin/bash", "-c", f"nohup python3 {self.STREAM_AGENT_CONTAINER_PATH} > /tmp/agent.log 2>&1 &"],
            detach=True,
            environment={"STREAM_AGENT_PORT": str(self.STREAM_AGENT_PORT)},
        )
        import time
        time.sleep(1)  # Give the agent a moment to start
        logger.info("Stream agent deployed to sandbox %s", container.name)

    def get_stream_port(self, sandbox_id: str) -> int:
        logger.info("Resolving stream port for sandbox %s", sandbox_id)
        """Resolve the host-side port Docker mapped to the agent."""
        container = self.client.containers.get(sandbox_id)
        container.reload()
        ports = container.attrs["NetworkSettings"]["Ports"]
        mapping = ports.get(f"{self.STREAM_AGENT_PORT}/tcp")
        if not mapping or not mapping[0].get("HostPort"):
            raise RuntimeError(f"Stream agent port not published for sandbox {sandbox_id}")
        return int(mapping[0]["HostPort"])

    def _ensure_network(self):
        try:
            if not self.client.networks.list(names=[self.SANDBOX_NETWORK]):
                self.client.networks.create(self.SANDBOX_NETWORK, driver="bridge")
        except Exception:
            pass

    def _resolve_image(self, environment: str) -> str:
        from gateway.core.sandbox.environments import ENVIRONMENT_TEMPLATES
        env_config = ENVIRONMENT_TEMPLATES.get(environment)
        image = env_config["image"] if env_config else "python:3.12-slim"
        try:
            self.client.images.get(image)
        except Exception:
            logger.info("Pulling image: %s", image)
            self.client.images.pull(image)
        return image

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

_orchestrator: SandboxOrchestrator | None = None
def get_orchestrator() -> SandboxOrchestrator:
    global _orchestrator
    if _orchestrator is None: _orchestrator = SandboxOrchestrator()
    return _orchestrator
