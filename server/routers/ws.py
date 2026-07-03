"""WebSocket API router for real-time updates."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

GATEWAY_ROOT = Path(__file__).resolve().parents[2] / "gateway"
if str(GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(GATEWAY_ROOT))

from core.git.cloner import CloneStatus, get_clone_service
from gateway.core.events import get_pipeline_event_bus

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/index/{job_id}")
async def index_progress_ws(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time indexing progress.
    Connect to: ws://localhost:8000/ws/index/{job_id}
    """
    await websocket.accept()
    service = get_clone_service()

    try:
        while True:
            job = service.get_job(job_id)

            if not job:
                await websocket.send_json({
                    "status": "error",
                    "message": f"Job {job_id} not found",
                    "error": "job_not_found"
                })
                break

            # Send current status
            await websocket.send_json({
                "status": job.status.value,
                "message": job.progress_message,
                "files_indexed": job.files_indexed,
                "entities_found": job.entities_found,
                "project_id": job.project_id,
                "folder_name": job.folder_name,
                "subdirectory": job.subdirectory,
                "clone_path": job.clone_path,
                "index_path": job.index_path,
                "error": job.error,
            })

            # Stop streaming when job is done
            if job.status in [CloneStatus.COMPLETE, CloneStatus.FAILED]:
                break

            # Poll every 2 seconds
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        pass
    finally:
        if websocket.application_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except RuntimeError as exc:
                if 'Cannot call "send" once a close message has been sent' not in str(exc):
                    raise


@router.websocket("/chat/{session_id}")
async def chat_pipeline_ws(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for live chat pipeline events.
    Connect to: ws://localhost:8000/ws/chat/{session_id}?after_seq=0
    """
    after_seq = 0
    try:
        after_seq = int(websocket.query_params.get("after_seq", "0"))
    except ValueError:
        after_seq = 0

    await websocket.accept()
    bus = get_pipeline_event_bus()

    try:
        async for event in bus.subscribe(session_id, after_seq=after_seq):
            await websocket.send_json(event)
            if event.get("stage") in {"done", "pipeline_failed"}:
                break
    except WebSocketDisconnect:
        pass
    finally:
        if websocket.application_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except RuntimeError as exc:
                if 'Cannot call "send" once a close message has been sent' not in str(exc):
                    raise
