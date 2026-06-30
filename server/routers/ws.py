"""WebSocket API router for real-time updates."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.git.cloner import CloneStatus, get_clone_service

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
        await websocket.close()
