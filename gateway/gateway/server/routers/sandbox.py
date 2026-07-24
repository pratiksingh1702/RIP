"""Sandbox REST + WebSocket API endpoints."""
from __future__ import annotations
import asyncio, json, logging
from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from gateway.core.sandbox.orchestrator import get_orchestrator
from gateway.core.sandbox.session import get_session_manager
from gateway.core.sandbox.terminal import get_terminal_manager
from gateway.core.sandbox.security import get_security_policy
from gateway.core.sandbox.environments import get_environment_registry
from gateway.core.sandbox.filesystem import SandboxFilesystem
from gateway.core.sandbox.snapshots import get_snapshot_manager
from gateway.core.sandbox.remote_machine import get_remote_connector
from gateway.server.request_context import gateway_user_id
from gateway.server.schemas.sandbox_requests import (
    CreateSandboxRequest, TerminalInputRequest, TerminalApproveRequest,
    FileWriteRequest, SnapshotRequest, RemoteConnectRequest
)

logger = logging.getLogger(__name__)
router = APIRouter()
_approval_events: dict[str, asyncio.Event] = {}

@router.post("/create")
async def create_sandbox(request: Request, body: CreateSandboxRequest):
    try:
        user_id = gateway_user_id(request) or "anonymous"
        orch = get_orchestrator()
        result = await orch.create_sandbox(body.project_id, user_id, body.environment, body.custom_config)
        session_mgr = get_session_manager()
        session = session_mgr.create_session(result["sandbox_id"], body.project_id, user_id)
        result["session_id"] = session.session_id
        return result
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{sandbox_id}")
async def sandbox_status(sandbox_id: str):
    orch = get_orchestrator()
    status = await orch.get_sandbox_status(sandbox_id)
    if status is None: raise HTTPException(status_code=404, detail="Sandbox not found")
    return status

@router.get("/list")
async def list_sandboxes(request: Request, project_id: str | None = Query(None)):
    user_id = gateway_user_id(request) or "anonymous"
    return await get_orchestrator().list_sandboxes(project_id=project_id, user_id=user_id)

@router.post("/{sandbox_id}/stop")
async def stop_sandbox(sandbox_id: str):
    ok = await get_orchestrator().stop_sandbox(sandbox_id)
    return {"sandbox_id": sandbox_id, "stopped": ok}

@router.post("/{sandbox_id}/start")
async def start_sandbox(sandbox_id: str):
    ok = await get_orchestrator().start_sandbox(sandbox_id)
    return {"sandbox_id": sandbox_id, "started": ok}

@router.delete("/{sandbox_id}")
async def destroy_sandbox(sandbox_id: str):
    ok = await get_orchestrator().destroy_sandbox(sandbox_id)
    return {"sandbox_id": sandbox_id, "destroyed": ok}

@router.get("/environments")
async def list_environments():
    return {"environments": get_environment_registry().list_environments()}

@router.get("/{sandbox_id}/files")
async def list_files(sandbox_id: str, path: str = "/workspace"):
    try:
        fs = SandboxFilesystem(sandbox_id)
        return {"files": fs.list_files(path)}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.get("/{sandbox_id}/files/read")
async def read_file(sandbox_id: str, path: str):
    try:
        fs = SandboxFilesystem(sandbox_id)
        ok, content = fs.read_file(path)
        if not ok: raise HTTPException(status_code=404, detail="File not found")
        return {"path": path, "content": content}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.put("/{sandbox_id}/files/write")
async def write_file(sandbox_id: str, body: FileWriteRequest):
    try:
        fs = SandboxFilesystem(sandbox_id)
        ok = fs.write_file(body.path, body.content)
        return {"path": body.path, "written": ok}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/{sandbox_id}/snapshot")
async def create_snapshot(sandbox_id: str, body: SnapshotRequest):
    try:
        result = await get_snapshot_manager().create_snapshot(sandbox_id, body.label)
        return result
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.get("/{sandbox_id}/snapshots")
async def list_snapshots(sandbox_id: str):
    return {"snapshots": await get_snapshot_manager().list_snapshots(sandbox_id)}

@router.post("/{sandbox_id}/restore/{snapshot_id}")
async def restore_snapshot(sandbox_id: str, snapshot_id: str):
    ok = await get_snapshot_manager().restore_snapshot(sandbox_id, snapshot_id)
    return {"sandbox_id": sandbox_id, "snapshot_id": snapshot_id, "restored": ok}

@router.post("/remote/connect")
async def connect_remote(request: Request, body: RemoteConnectRequest):
    try:
        user_id = gateway_user_id(request) or "anonymous"
        result = await get_remote_connector().connect(user_id, body.machine_url, body.api_key)
        return result
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/remote/disconnect")
async def disconnect_remote(request: Request):
    user_id = gateway_user_id(request) or "anonymous"
    ok = await get_remote_connector().disconnect(f"remote-{user_id}")
    return {"disconnected": ok}

@router.get("/remote/status")
async def remote_status(request: Request):
    user_id = gateway_user_id(request) or "anonymous"
    conn = get_remote_connector().get_connection(user_id)
    return {"connected": conn is not None, "connection": conn}

@router.websocket("/{sandbox_id}/terminal/{session_id}")
async def terminal_websocket(websocket: WebSocket, sandbox_id: str, session_id: str):
    await websocket.accept()
    user_id = "ws-user"
    project_id = "ws-project"
    term_mgr = get_terminal_manager()
    terminal = term_mgr.create_terminal(sandbox_id, session_id, user_id, project_id)
    await terminal.start()
    queue = await terminal.subscribe()

    try:
        consumer = asyncio.create_task(_consume_terminal_output(queue, websocket))
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "")
            if msg_type == "input":
                command = msg.get("command", "")
                if not command: continue
                security = get_security_policy()
                allowed, reason, risk = security.validate_command(command)
                if not allowed:
                    await websocket.send_json({"type": "blocked", "reason": reason})
                    continue
                if security.needs_approval(risk):
                    event = asyncio.Event()
                    _approval_events[terminal.terminal_id] = event
                    await websocket.send_json({"type": "approval_needed", "command": security.sanitize_for_logging(command), "reason": reason, "risk": risk.value})
                    try:
                        await asyncio.wait_for(event.wait(), timeout=300.0)
                        approved = getattr(event, '_approved', False)
                        if approved:
                            await terminal.execute_approved_command(command)
                        else:
                            await websocket.send_json({"type": "command_rejected", "command": security.sanitize_for_logging(command)})
                    except asyncio.TimeoutError:
                        await websocket.send_json({"type": "approval_timeout", "command": security.sanitize_for_logging(command)})
                    finally:
                        _approval_events.pop(terminal.terminal_id, None)
                else:
                    await terminal.write(command)
            elif msg_type == "approve":
                cmd = msg.get("command", "")
                if terminal.terminal_id in _approval_events:
                    evt = _approval_events[terminal.terminal_id]
                    evt._approved = True
                    evt.set()
                    await terminal.execute_approved_command(cmd)
            elif msg_type == "reject":
                if terminal.terminal_id in _approval_events:
                    evt = _approval_events[terminal.terminal_id]
                    evt._approved = False
                    evt.set()
    except WebSocketDisconnect: logger.info("Terminal WS disconnected: %s", terminal.terminal_id)
    except Exception as e: logger.error("Terminal WS error: %s", e)
    finally:
        consumer.cancel()
        terminal.unsubscribe(queue)
        await terminal.stop()
        term_mgr.remove_terminal(terminal.terminal_id)
        try: await websocket.close()
        except: pass

async def _consume_terminal_output(queue: asyncio.Queue, websocket: WebSocket):
    while True:
        msg = await queue.get()
        try: await websocket.send_json(msg)
        except: break
