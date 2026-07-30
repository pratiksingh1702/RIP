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

            # Send current status with logs & detailed progress
            await websocket.send_json({
                "job_id": job.job_id,
                "project_name": job.project_name,
                "git_url": job.git_url,
                "branch": job.branch,
                "status": job.status.value,
                "progress_message": job.progress_message,
                "files_indexed": job.files_indexed,
                "entities_found": job.entities_found,
                "project_id": job.project_id,
                "folder_name": job.folder_name,
                "subdirectory": job.subdirectory,
                "clone_path": job.clone_path,
                "index_path": job.index_path,
                "error": job.error,
                "logs": job.logs,
            })

            # Stop streaming when job is done
            if job.status in [CloneStatus.COMPLETE, CloneStatus.FAILED]:
                break

            # Push updates at 4Hz (every 0.25s) for instant telemetry
            await asyncio.sleep(0.25)

    except WebSocketDisconnect:
        pass
    finally:
        if websocket.application_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except RuntimeError as exc:
                if 'Cannot call "send" once a close message has been sent' not in str(exc):
                    raise


@router.websocket("/jobs")
async def all_jobs_ws(websocket: WebSocket):
    """
    WebSocket endpoint for live real-time pushing of all Git indexing jobs.
    Connect to: ws://localhost:8000/ws/jobs
    """
    await websocket.accept()
    service = get_clone_service()

    try:
        while True:
            jobs = service.get_all_jobs()
            jobs_data = [
                {
                    "job_id": j.job_id,
                    "git_url": j.git_url,
                    "project_name": j.project_name,
                    "folder_name": j.folder_name,
                    "branch": j.branch,
                    "status": j.status.value,
                    "progress_message": j.progress_message,
                    "project_id": j.project_id,
                    "clone_path": j.clone_path,
                    "index_path": j.index_path,
                    "files_indexed": j.files_indexed,
                    "entities_found": j.entities_found,
                    "error": j.error,
                    "logs": j.logs,
                }
                for j in jobs
            ]

            await websocket.send_json(jobs_data)
            await asyncio.sleep(0.25)

    except WebSocketDisconnect:
        pass
    finally:
        if websocket.application_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except RuntimeError:
                pass


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
