# RIP — Remote Working, Git Intelligence & Flutter App
## Complete Phase Plan for Agent

---

## READ THIS ENTIRE DOCUMENT BEFORE WRITING A SINGLE LINE OF CODE

This plan has two phases. Phase 1 is the remote-working architecture — making RIP work without local file setup, indexing repositories directly from Git URLs, exposing everything through a clean REST API. Phase 2 is the Flutter mobile app that connects to the server and lets anyone query any indexed repository from their phone.

Do not start Phase 2 until Phase 1 is fully verified and all endpoints are responding correctly.

---

## THE CURRENT STATE — WHAT ALREADY EXISTS

Everything below is already built and working. Do not rebuild any of it.

- RIP Core: parser layer, Neo4j graph, Qdrant vectors, PostgreSQL metadata, Redis cache
- All CLI commands: `repo index`, `repo trace`, `repo impact`, `repo search`, `repo explain`, `repo architecture`, `repo onboard`, `repo metrics`, `repo dead-code`, `repo dependencies`, `repo delete`
- FastAPI server at port 8000 with endpoints: `/index`, `/search`, `/explain`, `/trace/{symbol}`, `/impact/{symbol}`, `/architecture`, `/dead-code`, `/metrics`, `/onboard`, `/health`
- Context Gateway at port 8001 with MCP tools and REST API
- VS Code extension with chat panel
- Multi-language parsers: Python, TypeScript, Java, Go, Rust, Dart/Flutter

---

## THE CORE INSIGHT BEFORE BUILDING ANYTHING

Right now RIP requires the user to:
1. Have the repository on their local machine
2. Run `repo index /path/to/repo`
3. Have Docker running locally
4. Have the FastAPI server running locally

This is fine for a developer working on their own machine. It is completely useless for:
- A developer on their phone who wants to understand a codebase
- A team that wants shared indexed knowledge of their repositories
- Anyone who does not want to set up Docker and all dependencies

The transformation is simple: instead of indexing a local path, index a Git URL. Instead of requiring local setup, run RIP as a server that anyone with the URL and an API key can query. The intelligence stays in Neo4j and Qdrant on the server. Clients — CLI, mobile app, web — just send queries.

After indexing `https://github.com/user/repo`, the source files are no longer needed. Everything worth knowing is in Neo4j (graph) and Qdrant (vectors). The server answers questions from those databases forever. Source files can be deleted after indexing.

---

## PHASE 1 — REMOTE WORKING AND GIT INDEXING

### What Phase 1 Produces

A running RIP server that anyone can point at, give a Git URL, and get back intelligence about that repository — with no local setup required on the client side.

```
BEFORE (today):
  Developer → Clone repo → Install RIP → Run Docker → repo index path → query

AFTER (Phase 1):
  Developer → POST /git/index {url} → wait 2-5 min → query forever
  Mobile user → GET /query/search {project_id, q} → get answer
  AI agent → call get_context → get context package
```

---

## PHASE 1 — TASK LIST

### Task 1.1 — Create the Git Clone Service

**File to create:** `core/git/cloner.py`

**What it does:** Given a Git URL, clones the repository to a temporary location on the server's disk, runs the full indexing pipeline, then optionally deletes the clone.

```python
# core/git/cloner.py

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class CloneStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    INDEXING = "indexing"
    COMPLETE = "complete"
    FAILED = "failed"

@dataclass
class CloneJob:
    job_id: str
    git_url: str
    project_name: str
    branch: str
    status: CloneStatus
    project_id: str | None = None
    error: str | None = None
    progress_message: str = ""
    files_indexed: int = 0
    entities_found: int = 0

class GitCloneService:
    """
    Clones a git repository to a temp folder,
    runs the RIP indexing pipeline,
    then removes the clone.
    The graph and vectors persist in Neo4j and Qdrant.
    """
    
    # Store active jobs in memory
    # In production this would be PostgreSQL
    _jobs: dict[str, CloneJob] = {}
    
    async def start_clone_and_index(
        self,
        git_url: str,
        project_name: str,
        branch: str = "main",
        keep_clone: bool = False
    ) -> str:
        """
        Start a clone-and-index job.
        Returns job_id immediately.
        Job runs in the background.
        """
        job_id = str(uuid.uuid4())
        
        job = CloneJob(
            job_id=job_id,
            git_url=git_url,
            project_name=project_name,
            branch=branch,
            status=CloneStatus.PENDING,
        )
        self._jobs[job_id] = job
        
        # Run in background so we can return immediately
        asyncio.create_task(
            self._clone_and_index(job, keep_clone)
        )
        
        return job_id
    
    async def _clone_and_index(self, job: CloneJob, keep_clone: bool):
        """Background task: clone → index → cleanup."""
        
        clone_path = None
        
        try:
            # Step 1: Clone
            job.status = CloneStatus.CLONING
            job.progress_message = f"Cloning {job.git_url}..."
            
            clone_path = Path(tempfile.mkdtemp()) / f"rip_{job.job_id}"
            
            # Use git subprocess — asyncio-safe
            result = await asyncio.create_subprocess_exec(
                "git", "clone",
                "--branch", job.branch,
                "--depth", "1",  # Shallow clone for speed
                "--single-branch",
                str(job.git_url),
                str(clone_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"Git clone failed: {stderr.decode()[:500]}"
                )
            
            job.progress_message = "Clone complete. Starting indexing..."
            
            # Step 2: Initialize RIP project
            job.status = CloneStatus.INDEXING
            
            from core.indexer.pipeline import index_repository_with_resources
            from core.graph.client import Neo4jClient
            from server.config import get_settings
            
            settings = get_settings()
            
            # Use project_name as project identifier
            project_id = f"{job.project_name.lower().replace(' ', '-')}-{job.job_id[:8]}"
            job.project_id = project_id
            
            # Run the existing indexing pipeline
            # This writes to Neo4j and Qdrant with the project_id
            async with Neo4jClient(settings.neo4j_uri, ...) as client:
                summary = await index_repository_with_resources(
                    repo_path=str(clone_path),
                    client=client,
                    project_id=project_id,
                    project_name=job.project_name,
                )
            
            job.files_indexed = summary.indexed_files
            job.entities_found = summary.total_entities
            job.status = CloneStatus.COMPLETE
            job.progress_message = (
                f"Indexed {summary.indexed_files} files, "
                f"{summary.total_entities} entities"
            )
            
        except Exception as e:
            job.status = CloneStatus.FAILED
            job.error = str(e)
            job.progress_message = f"Failed: {e}"
        
        finally:
            # Step 3: Clean up clone (source files no longer needed)
            if clone_path and clone_path.exists() and not keep_clone:
                shutil.rmtree(clone_path, ignore_errors=True)
    
    def get_job(self, job_id: str) -> CloneJob | None:
        return self._jobs.get(job_id)
    
    def get_all_jobs(self) -> list[CloneJob]:
        return list(self._jobs.values())


# Global singleton
_clone_service = GitCloneService()

def get_clone_service() -> GitCloneService:
    return _clone_service
```

**Verification:**
```python
# Test that the service works end to end
import asyncio
from core.git.cloner import get_clone_service

async def test():
    service = get_clone_service()
    job_id = await service.start_clone_and_index(
        git_url="https://github.com/pallets/flask",
        project_name="flask-test",
        branch="main"
    )
    print(f"Job started: {job_id}")
    
    # Poll until complete
    import time
    while True:
        job = service.get_job(job_id)
        print(f"Status: {job.status} — {job.progress_message}")
        if job.status in ["complete", "failed"]:
            break
        await asyncio.sleep(5)

asyncio.run(test())
```

---

### Task 1.2 — Create the Git Indexing Router

**File to create:** `server/routers/git.py`

**What it does:** Exposes the Git clone service as HTTP endpoints.

```python
# server/routers/git.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from core.git.cloner import get_clone_service, CloneStatus

router = APIRouter(prefix="/git", tags=["git"])


class IndexGitRequest(BaseModel):
    git_url: str               # Full git URL: https://github.com/user/repo.git
    project_name: str          # Human-readable name: "my-payment-service"
    branch: str = "main"       # Branch to clone
    keep_clone: bool = False   # Keep source files after indexing (for re-index)


class IndexGitResponse(BaseModel):
    job_id: str
    project_name: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    git_url: str
    project_name: str
    branch: str
    status: str
    progress_message: str
    project_id: str | None
    files_indexed: int
    entities_found: int
    error: str | None


@router.post("/index", response_model=IndexGitResponse)
async def start_git_index(request: IndexGitRequest):
    """
    Clone a Git repository and index it into RIP.
    Returns immediately with a job_id.
    Poll /git/status/{job_id} to track progress.
    
    The source files are deleted after indexing.
    Intelligence is permanently stored in Neo4j and Qdrant.
    """
    service = get_clone_service()
    
    job_id = await service.start_clone_and_index(
        git_url=request.git_url,
        project_name=request.project_name,
        branch=request.branch,
        keep_clone=request.keep_clone,
    )
    
    return IndexGitResponse(
        job_id=job_id,
        project_name=request.project_name,
        status="started",
        message=(
            f"Cloning {request.git_url} and indexing. "
            f"Poll /git/status/{job_id} for progress."
        )
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the current status of a Git indexing job.
    Status transitions: pending → cloning → indexing → complete/failed
    """
    service = get_clone_service()
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        git_url=job.git_url,
        project_name=job.project_name,
        branch=job.branch,
        status=job.status.value,
        progress_message=job.progress_message,
        project_id=job.project_id,
        files_indexed=job.files_indexed,
        entities_found=job.entities_found,
        error=job.error,
    )


@router.get("/jobs", response_model=list[JobStatusResponse])
async def list_jobs():
    """List all Git indexing jobs (active and completed)."""
    service = get_clone_service()
    jobs = service.get_all_jobs()
    
    return [
        JobStatusResponse(
            job_id=j.job_id,
            git_url=j.git_url,
            project_name=j.project_name,
            branch=j.branch,
            status=j.status.value,
            progress_message=j.progress_message,
            project_id=j.project_id,
            files_indexed=j.files_indexed,
            entities_found=j.entities_found,
            error=j.error,
        )
        for j in jobs
    ]
```

**Register in `server/app.py`:**
```python
from server.routers.git import router as git_router
app.include_router(git_router)
```

**Verification:**
```bash
# Start the server
uv run repo serve --port 8000

# Start indexing Flask
curl -X POST http://localhost:8000/git/index \
  -H "Content-Type: application/json" \
  -d '{"git_url": "https://github.com/pallets/flask", "project_name": "flask", "branch": "main"}'

# Response:
# {"job_id": "abc-123", "status": "started", ...}

# Poll status
curl http://localhost:8000/git/status/abc-123

# Wait for status: "complete"
```

---

### Task 1.3 — Create the Projects Router

**File to create:** `server/routers/projects.py`

**What it does:** Lists all indexed projects so clients can discover what is available to query.

```python
# server/routers/projects.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.storage.project_store import get_all_projects, get_project_by_id, delete_project

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectResponse(BaseModel):
    project_id: str
    project_name: str
    indexed_at: str
    files_count: int
    entities_count: int
    languages: list[str]
    git_url: str | None = None


@router.get("/", response_model=list[ProjectResponse])
async def list_projects():
    """
    List all indexed repositories.
    Used by clients to discover what they can query.
    """
    projects = await get_all_projects()
    return [
        ProjectResponse(
            project_id=p.project_id,
            project_name=p.project_name,
            indexed_at=p.indexed_at.isoformat() if p.indexed_at else "",
            files_count=p.files_count or 0,
            entities_count=p.entities_count or 0,
            languages=p.languages or [],
            git_url=p.git_url,
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """Get details of a specific indexed project."""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    return ProjectResponse(
        project_id=project.project_id,
        project_name=project.project_name,
        indexed_at=project.indexed_at.isoformat() if project.indexed_at else "",
        files_count=project.files_count or 0,
        entities_count=project.entities_count or 0,
        languages=project.languages or [],
        git_url=project.git_url,
    )


@router.delete("/{project_id}")
async def remove_project(project_id: str):
    """
    Delete a project and all its indexed data.
    Removes Neo4j nodes, Qdrant vectors, and PostgreSQL metadata.
    """
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    await delete_project(project_id)
    
    return {"message": f"Project {project_id} deleted", "project_name": project.project_name}
```

**Register in `server/app.py`:**
```python
from server.routers.projects import router as projects_router
app.include_router(projects_router)
```

**Verification:**
```bash
# After indexing Flask from Task 1.2:
curl http://localhost:8000/projects/

# Expected:
# [{"project_id": "flask-abc123", "project_name": "flask", "files_count": 847, ...}]
```

---

### Task 1.4 — Fix Project Isolation on All Existing Endpoints

**Problem identified in the audit:** `/trace/{symbol}`, `/impact/{symbol}`, `/architecture`, `/dead-code`, `/metrics`, `/onboard` do not pass `project_id` through to the core functions. This means on a server with multiple indexed projects, queries return results from the wrong project.

**Files to modify:**

```
server/routers/trace.py      — add project_id query param
server/routers/impact.py     — add project_id query param
server/routers/architecture.py — add project_id query param
server/routers/analysis.py   — add project_id query param (dead-code, metrics)
server/routers/onboard.py    — add project_id query param
```

**Pattern to apply to every router:**

```python
# Before (broken for multi-project):
@router.get("/trace/{symbol}")
async def trace_symbol(symbol: str, explain: bool = Query(False)):
    result = await trace_query(symbol)  # Uses default project!
    ...

# After (project-safe):
@router.get("/trace/{symbol}")
async def trace_symbol(
    symbol: str,
    project_id: str = Query(None, description="Project ID to query. Get from /projects/"),
    explain: bool = Query(False),
):
    result = await trace_query(symbol, project_id=project_id)
    ...
```

Do this for every endpoint. `project_id` is always optional (defaults to the most recently indexed project for backwards compatibility) but should be passed through to every core function call.

**Verification:**
```bash
# Index two different projects
curl -X POST http://localhost:8000/git/index \
  -d '{"git_url": "https://github.com/pallets/flask", "project_name": "flask"}'

curl -X POST http://localhost:8000/git/index \
  -d '{"git_url": "https://github.com/tiangolo/fastapi", "project_name": "fastapi"}'

# Wait for both to complete, then:

# Get projects
curl http://localhost:8000/projects/
# Note the two project_ids

# Query Flask specifically
curl "http://localhost:8000/search?q=routing&project_id=flask-abc123"

# Query FastAPI specifically
curl "http://localhost:8000/search?q=routing&project_id=fastapi-def456"

# Results should be different — Flask routes vs FastAPI routes
```

---

### Task 1.5 — Add API Key Authentication

**Problem:** The server currently has no authentication. Anyone with the URL can index and query repositories.

**File to create:** `server/middleware/auth.py`

```python
# server/middleware/auth.py

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import secrets

# API keys stored in environment variable or PostgreSQL
# For Phase 1, environment variable is sufficient
# Format: comma-separated list of keys
# GATEWAY_API_KEYS=key1,key2,key3

def get_valid_api_keys() -> set[str]:
    """Load valid API keys from environment."""
    keys_str = os.getenv("RIP_API_KEYS", "")
    if not keys_str:
        # If no keys configured, allow all requests (development mode)
        return set()
    return set(k.strip() for k in keys_str.split(",") if k.strip())


async def verify_api_key(request: Request):
    """
    Middleware: verify API key in Authorization header.
    Skip verification if no API keys are configured (development mode).
    """
    valid_keys = get_valid_api_keys()
    
    if not valid_keys:
        # Development mode — no authentication required
        return
    
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include 'Authorization: Bearer YOUR_KEY' header."
        )
    
    provided_key = auth_header[7:]  # Remove "Bearer "
    
    if provided_key not in valid_keys:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key."
        )
```

**Add to `server/app.py`:**
```python
from fastapi import Depends
from server.middleware.auth import verify_api_key

# Apply to all routes except /health
app.include_router(git_router, dependencies=[Depends(verify_api_key)])
app.include_router(projects_router, dependencies=[Depends(verify_api_key)])
# ... same for all other routers
```

**Add key generation helper:**
```python
# In server/app.py or as a CLI command
import secrets
print(secrets.token_urlsafe(32))
# Generates a key like: xK9mN2pQr7sT4uV1wX5yZ8aB3cD6eF0
```

**Verification:**
```bash
# Without API key (returns 401)
curl http://localhost:8000/projects/

# With API key (returns projects)
curl -H "Authorization: Bearer your-key-here" http://localhost:8000/projects/

# Health endpoint always works (no auth needed)
curl http://localhost:8000/health
```

---

### Task 1.6 — Add WebSocket Progress for Indexing

**Problem:** Clients (especially the Flutter app) need real-time progress during indexing. HTTP polling works but feels clunky. WebSocket is cleaner.

**File to create:** `server/routers/ws.py`

```python
# server/routers/ws.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.git.cloner import get_clone_service, CloneStatus
import asyncio
import json

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/index/{job_id}")
async def index_progress_ws(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time indexing progress.
    
    Connect to: ws://localhost:8000/ws/index/{job_id}
    
    Receives JSON messages:
    {
        "status": "cloning" | "indexing" | "complete" | "failed",
        "message": "Cloning https://...",
        "files_indexed": 0,
        "entities_found": 0,
        "progress_pct": 45,
        "error": null
    }
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
```

**Register in `server/app.py`:**
```python
from server.routers.ws import router as ws_router
app.include_router(ws_router)
```

**Verification:**
```python
# Python WebSocket test
import asyncio
import websockets
import json

async def test():
    job_id = "your-job-id-here"
    async with websockets.connect(f"ws://localhost:8000/ws/index/{job_id}") as ws:
        async for message in ws:
            data = json.loads(message)
            print(f"{data['status']}: {data['message']}")
            if data['status'] in ['complete', 'failed']:
                break

asyncio.run(test())
```

---

### Task 1.7 — Update the Project Store for Git URLs

**File to modify:** `core/storage/models.py` (or wherever the Project model lives)

Add `git_url`, `files_count`, `entities_count`, and `languages` fields to the Project ORM model.

```python
# In the Project ORM model
class Project(Base):
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    project_name: Mapped[str] = mapped_column(String(255))
    
    # NEW FIELDS — add these
    git_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    files_count: Mapped[int] = mapped_column(Integer, default=0)
    entities_count: Mapped[int] = mapped_column(Integer, default=0)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    
    indexed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_reindexed_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

Run migration:
```bash
uv run alembic revision --autogenerate -m "add git url and stats to projects"
uv run alembic upgrade head
```

---

### Task 1.8 — Update the GitCloneService to Persist Project to PostgreSQL

**Modify:** `core/git/cloner.py`

After successful indexing, write the project record to PostgreSQL with the git_url, files_count, entities_count, and languages detected.

```python
# In _clone_and_index, after indexing completes:

from core.storage.project_store import upsert_project

await upsert_project(
    project_id=project_id,
    project_name=job.project_name,
    git_url=job.git_url,
    branch=job.branch,
    files_count=summary.indexed_files,
    entities_count=summary.total_entities,
    languages=summary.languages_detected,
)
```

---

### Task 1.9 — Phase 1 Complete Verification

Run all of these in sequence. Every single one must pass before starting Phase 2.

```bash
# 1. Start Docker services
docker-compose up -d
sleep 20

# 2. Start RIP server
uv run repo serve --host 0.0.0.0 --port 8000 &
sleep 5

# 3. Health check
curl http://localhost:8000/health
# Expected: {"status": "ok", "neo4j": true, "qdrant": true}

# 4. Index a real repository
curl -X POST http://localhost:8000/git/index \
  -H "Content-Type: application/json" \
  -d '{"git_url": "https://github.com/pallets/flask", "project_name": "flask", "branch": "main"}'

# Save the job_id from response
JOB_ID="abc-123"  # Replace with actual

# 5. Poll until complete (check every 30 seconds for 10 minutes)
while true; do
  STATUS=$(curl -s http://localhost:8000/git/status/$JOB_ID | python -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  if [ "$STATUS" = "complete" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 30
done

# 6. Get the project_id from status
PROJECT_ID=$(curl -s http://localhost:8000/git/status/$JOB_ID | python -c "import sys,json; print(json.load(sys.stdin)['project_id'])")

# 7. List projects — should show Flask
curl http://localhost:8000/projects/

# 8. Search within Flask project
curl "http://localhost:8000/search?q=routing&project_id=$PROJECT_ID"

# 9. Trace within Flask project
curl "http://localhost:8000/trace/Flask?project_id=$PROJECT_ID"

# 10. Architecture within Flask project
curl "http://localhost:8000/architecture?project_id=$PROJECT_ID"

# 11. Test linter
uv run ruff check server/routers/git.py server/routers/projects.py core/git/cloner.py

# 12. Index a second project to verify isolation
curl -X POST http://localhost:8000/git/index \
  -H "Content-Type: application/json" \
  -d '{"git_url": "https://github.com/psf/requests", "project_name": "requests", "branch": "main"}'

# Wait for completion, then verify results differ between projects
```

---

## PHASE 2 — FLUTTER MOBILE APP

**DO NOT START THIS PHASE UNTIL PHASE 1 IS COMPLETE AND VERIFIED.**

All verification commands in Task 1.9 must pass before writing a single Flutter file.

---

## WHAT THE FLUTTER APP DOES

The Flutter app connects to a running RIP server and lets anyone:
- Browse all indexed repositories
- Add a new repository by Git URL
- Watch real-time indexing progress
- Search any indexed repository semantically
- Trace call chains
- View impact analysis
- Ask questions in natural language
- See architecture diagrams

The app is a client. It calls the RIP server REST API. It stores no intelligence locally. Everything is on the server.

---

## FLUTTER APP FILE STRUCTURE

Create this structure. Every file is either a Dart file or a config file.

```
rip_app/
├── pubspec.yaml
├── lib/
│   ├── main.dart
│   │
│   ├── core/
│   │   ├── api/
│   │   │   ├── rip_client.dart          # HTTP client for RIP server
│   │   │   ├── models/
│   │   │   │   ├── project.dart         # Project model
│   │   │   │   ├── search_result.dart   # Search result model
│   │   │   │   ├── trace_result.dart    # Trace result model
│   │   │   │   ├── impact_result.dart   # Impact result model
│   │   │   │   └── git_job.dart         # Git indexing job model
│   │   │   └── exceptions.dart          # API exception types
│   │   │
│   │   ├── config/
│   │   │   ├── app_config.dart          # Server URL, API key storage
│   │   │   └── theme.dart               # App colors and typography
│   │   │
│   │   └── providers/
│   │       ├── projects_provider.dart   # Riverpod provider for projects
│   │       ├── search_provider.dart     # Riverpod provider for search
│   │       └── index_provider.dart      # Riverpod provider for indexing jobs
│   │
│   ├── features/
│   │   ├── setup/
│   │   │   ├── setup_screen.dart        # First-time server URL configuration
│   │   │   └── setup_provider.dart
│   │   │
│   │   ├── projects/
│   │   │   ├── projects_screen.dart     # List of all indexed repositories
│   │   │   ├── project_card.dart        # Single project card widget
│   │   │   └── add_project_sheet.dart   # Bottom sheet to add new repo
│   │   │
│   │   ├── indexing/
│   │   │   ├── indexing_screen.dart     # Real-time indexing progress
│   │   │   ├── progress_card.dart       # Progress display widget
│   │   │   └── indexing_provider.dart   # WebSocket state management
│   │   │
│   │   ├── search/
│   │   │   ├── search_screen.dart       # Search interface with results
│   │   │   ├── search_result_tile.dart  # Single result display
│   │   │   └── search_provider.dart     # Search state management
│   │   │
│   │   ├── trace/
│   │   │   ├── trace_screen.dart        # Call chain visualization
│   │   │   ├── trace_node_widget.dart   # Single node in trace tree
│   │   │   └── trace_provider.dart
│   │   │
│   │   ├── impact/
│   │   │   ├── impact_screen.dart       # Impact analysis display
│   │   │   └── impact_provider.dart
│   │   │
│   │   ├── chat/
│   │   │   ├── chat_screen.dart         # Natural language Q&A interface
│   │   │   ├── chat_message.dart        # Single chat message widget
│   │   │   └── chat_provider.dart       # Chat state via Gateway
│   │   │
│   │   └── architecture/
│   │       ├── architecture_screen.dart # Architecture visualization
│   │       └── architecture_provider.dart
│   │
│   └── shared/
│       ├── widgets/
│       │   ├── rip_app_bar.dart         # Common app bar
│       │   ├── error_widget.dart        # Error display
│       │   ├── loading_widget.dart      # Loading indicator
│       │   └── code_block.dart          # Syntax-highlighted code display
│       └── navigation/
│           └── app_router.dart          # GoRouter navigation
│
├── test/
│   ├── api/
│   │   └── rip_client_test.dart
│   └── features/
│       └── projects_screen_test.dart
│
└── integration_test/
    └── app_test.dart
```

---

### Task 2.1 — pubspec.yaml

```yaml
name: rip_app
description: Repository Intelligence Platform — Mobile Client

publish_to: 'none'

version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  
  # State management
  flutter_riverpod: ^2.4.0
  riverpod_annotation: ^2.3.0
  
  # Navigation
  go_router: ^12.0.0
  
  # HTTP
  dio: ^5.4.0
  
  # WebSocket
  web_socket_channel: ^2.4.0
  
  # Local storage
  shared_preferences: ^2.2.0
  
  # UI
  flutter_markdown: ^0.6.18
  
  # Code highlighting
  flutter_highlight: ^0.7.0
  highlight: ^0.7.0
  
  # Icons
  cupertino_icons: ^1.0.2

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
  build_runner: ^2.4.0
  riverpod_generator: ^2.3.0
```

---

### Task 2.2 — The RIP API Client

**File:** `lib/core/api/rip_client.dart`

```dart
// lib/core/api/rip_client.dart

import 'package:dio/dio.dart';
import 'models/project.dart';
import 'models/search_result.dart';
import 'models/trace_result.dart';
import 'models/impact_result.dart';
import 'models/git_job.dart';

class RIPClient {
  late final Dio _dio;
  
  RIPClient({required String serverUrl, String? apiKey}) {
    _dio = Dio(BaseOptions(
      baseUrl: serverUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
    ));
    
    // Add API key header if provided
    if (apiKey != null && apiKey.isNotEmpty) {
      _dio.options.headers['Authorization'] = 'Bearer $apiKey';
    }
    
    // Add error interceptor
    _dio.interceptors.add(InterceptorsWrapper(
      onError: (error, handler) {
        if (error.response?.statusCode == 401) {
          throw RIPAuthException('Invalid or missing API key');
        }
        if (error.response?.statusCode == 404) {
          throw RIPNotFoundException(error.message ?? 'Not found');
        }
        handler.next(error);
      },
    ));
  }
  
  // ── Projects ──────────────────────────────────────────────────
  
  Future<List<RIPProject>> listProjects() async {
    final response = await _dio.get('/projects/');
    final List<dynamic> data = response.data as List;
    return data.map((j) => RIPProject.fromJson(j as Map<String, dynamic>)).toList();
  }
  
  Future<RIPProject> getProject(String projectId) async {
    final response = await _dio.get('/projects/$projectId');
    return RIPProject.fromJson(response.data as Map<String, dynamic>);
  }
  
  Future<void> deleteProject(String projectId) async {
    await _dio.delete('/projects/$projectId');
  }
  
  // ── Git Indexing ──────────────────────────────────────────────
  
  Future<GitIndexJob> startGitIndex({
    required String gitUrl,
    required String projectName,
    String branch = 'main',
  }) async {
    final response = await _dio.post('/git/index', data: {
      'git_url': gitUrl,
      'project_name': projectName,
      'branch': branch,
    });
    return GitIndexJob.fromJson(response.data as Map<String, dynamic>);
  }
  
  Future<GitIndexJob> getJobStatus(String jobId) async {
    final response = await _dio.get('/git/status/$jobId');
    return GitIndexJob.fromJson(response.data as Map<String, dynamic>);
  }
  
  // ── Search ────────────────────────────────────────────────────
  
  Future<List<SearchResult>> search({
    required String projectId,
    required String query,
    int limit = 10,
  }) async {
    final response = await _dio.get('/search', queryParameters: {
      'q': query,
      'project_id': projectId,
      'top': limit,
    });
    
    final data = response.data as Map<String, dynamic>;
    final List<dynamic> results = data['data'] as List? ?? [];
    return results
        .map((r) => SearchResult.fromJson(r as Map<String, dynamic>))
        .toList();
  }
  
  // ── Trace ─────────────────────────────────────────────────────
  
  Future<TraceResult> trace({
    required String projectId,
    required String symbol,
  }) async {
    final response = await _dio.get(
      '/trace/$symbol',
      queryParameters: {'project_id': projectId},
    );
    final data = response.data as Map<String, dynamic>;
    return TraceResult.fromJson(data['data'] as Map<String, dynamic>);
  }
  
  // ── Impact ────────────────────────────────────────────────────
  
  Future<ImpactResult> impact({
    required String projectId,
    required String symbol,
  }) async {
    final response = await _dio.get(
      '/impact/$symbol',
      queryParameters: {'project_id': projectId},
    );
    final data = response.data as Map<String, dynamic>;
    return ImpactResult.fromJson(data['data'] as Map<String, dynamic>);
  }
  
  // ── Architecture ──────────────────────────────────────────────
  
  Future<Map<String, dynamic>> architecture({required String projectId}) async {
    final response = await _dio.get(
      '/architecture',
      queryParameters: {'project_id': projectId},
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>;
  }
  
  // ── Explain ───────────────────────────────────────────────────
  
  Future<String> explain({
    required String projectId,
    required String topic,
  }) async {
    final response = await _dio.post('/explain', data: {
      'symbol': topic,
      'project_id': projectId,
    });
    final data = response.data as Map<String, dynamic>;
    final explanationData = data['data'] as Map<String, dynamic>?;
    return explanationData?['explanation'] as String? ?? 
           'No explanation available';
  }
  
  // ── Health ────────────────────────────────────────────────────
  
  Future<bool> healthCheck() async {
    try {
      final response = await _dio.get('/health');
      final data = response.data as Map<String, dynamic>;
      return data['status'] == 'ok' || data['status'] == 'healthy';
    } catch (_) {
      return false;
    }
  }
}

// Exceptions
class RIPAuthException implements Exception {
  final String message;
  RIPAuthException(this.message);
}

class RIPNotFoundException implements Exception {
  final String message;
  RIPNotFoundException(this.message);
}
```

---

### Task 2.3 — Data Models

**File:** `lib/core/api/models/project.dart`

```dart
class RIPProject {
  final String projectId;
  final String projectName;
  final String indexedAt;
  final int filesCount;
  final int entitiesCount;
  final List<String> languages;
  final String? gitUrl;

  const RIPProject({
    required this.projectId,
    required this.projectName,
    required this.indexedAt,
    required this.filesCount,
    required this.entitiesCount,
    required this.languages,
    this.gitUrl,
  });

  factory RIPProject.fromJson(Map<String, dynamic> json) => RIPProject(
    projectId: json['project_id'] as String,
    projectName: json['project_name'] as String,
    indexedAt: json['indexed_at'] as String? ?? '',
    filesCount: json['files_count'] as int? ?? 0,
    entitiesCount: json['entities_count'] as int? ?? 0,
    languages: (json['languages'] as List<dynamic>?)
        ?.map((l) => l as String)
        .toList() ?? [],
    gitUrl: json['git_url'] as String?,
  );
}
```

**File:** `lib/core/api/models/search_result.dart`

```dart
class SearchResult {
  final String entityId;
  final String entityType;
  final String name;
  final String filePath;
  final String language;
  final double score;
  final String? rawCode;

  const SearchResult({
    required this.entityId,
    required this.entityType,
    required this.name,
    required this.filePath,
    required this.language,
    required this.score,
    this.rawCode,
  });

  factory SearchResult.fromJson(Map<String, dynamic> json) => SearchResult(
    entityId: json['entity_id'] as String? ?? '',
    entityType: json['entity_type'] as String? ?? 'unknown',
    name: json['name'] as String? ?? '',
    filePath: json['file_path'] as String? ?? '',
    language: json['language'] as String? ?? '',
    score: (json['score'] as num?)?.toDouble() ?? 0.0,
    rawCode: json['raw_code'] as String?,
  );
}
```

**File:** `lib/core/api/models/git_job.dart`

```dart
class GitIndexJob {
  final String jobId;
  final String? gitUrl;
  final String? projectName;
  final String status;
  final String progressMessage;
  final String? projectId;
  final int filesIndexed;
  final int entitiesFound;
  final String? error;

  const GitIndexJob({
    required this.jobId,
    this.gitUrl,
    this.projectName,
    required this.status,
    required this.progressMessage,
    this.projectId,
    required this.filesIndexed,
    required this.entitiesFound,
    this.error,
  });

  bool get isComplete => status == 'complete';
  bool get isFailed => status == 'failed';
  bool get isInProgress => !isComplete && !isFailed;

  factory GitIndexJob.fromJson(Map<String, dynamic> json) => GitIndexJob(
    jobId: json['job_id'] as String,
    gitUrl: json['git_url'] as String?,
    projectName: json['project_name'] as String?,
    status: json['status'] as String? ?? 'pending',
    progressMessage: json['progress_message'] as String? ?? '',
    projectId: json['project_id'] as String?,
    filesIndexed: json['files_indexed'] as int? ?? 0,
    entitiesFound: json['entities_found'] as int? ?? 0,
    error: json['error'] as String?,
  );
}
```

---

### Task 2.4 — Setup Screen

**File:** `lib/features/setup/setup_screen.dart`

This is the first screen the user sees. They enter the server URL and API key.

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/api/rip_client.dart';

class SetupScreen extends ConsumerStatefulWidget {
  const SetupScreen({super.key});
  
  @override
  ConsumerState<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends ConsumerState<SetupScreen> {
  final _urlController = TextEditingController(
    text: 'http://localhost:8000',
  );
  final _keyController = TextEditingController();
  bool _isChecking = false;
  String? _errorMessage;
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 40),
              
              // Logo and title
              Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primary,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.hub, color: Colors.white, size: 28),
                  ),
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'RIP',
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      Text(
                        'Repository Intelligence',
                        style: Theme.of(context).textTheme.bodySmall
                            ?.copyWith(color: Colors.grey),
                      ),
                    ],
                  ),
                ],
              ),
              
              const SizedBox(height: 48),
              
              Text(
                'Connect to Server',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                'Enter your RIP server URL and API key to get started.',
                style: Theme.of(context).textTheme.bodyMedium
                    ?.copyWith(color: Colors.grey),
              ),
              
              const SizedBox(height: 32),
              
              // Server URL field
              TextField(
                controller: _urlController,
                decoration: const InputDecoration(
                  labelText: 'Server URL',
                  hintText: 'http://localhost:8000',
                  prefixIcon: Icon(Icons.dns),
                  border: OutlineInputBorder(),
                ),
                keyboardType: TextInputType.url,
              ),
              
              const SizedBox(height: 16),
              
              // API Key field
              TextField(
                controller: _keyController,
                decoration: const InputDecoration(
                  labelText: 'API Key (optional)',
                  hintText: 'Leave empty for development mode',
                  prefixIcon: Icon(Icons.key),
                  border: OutlineInputBorder(),
                ),
                obscureText: true,
              ),
              
              const SizedBox(height: 24),
              
              // Error message
              if (_errorMessage != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.red.shade200),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: Colors.red, size: 16),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: const TextStyle(color: Colors.red, fontSize: 13),
                        ),
                      ),
                    ],
                  ),
                ),
              
              if (_errorMessage != null) const SizedBox(height: 16),
              
              // Connect button
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _isChecking ? null : _connect,
                  child: _isChecking
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Connect'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
  
  Future<void> _connect() async {
    setState(() {
      _isChecking = true;
      _errorMessage = null;
    });
    
    final url = _urlController.text.trim();
    final key = _keyController.text.trim();
    
    if (url.isEmpty) {
      setState(() {
        _isChecking = false;
        _errorMessage = 'Server URL is required';
      });
      return;
    }
    
    // Test the connection
    try {
      final client = RIPClient(serverUrl: url, apiKey: key.isEmpty ? null : key);
      final isHealthy = await client.healthCheck();
      
      if (!isHealthy) {
        setState(() {
          _isChecking = false;
          _errorMessage = 'Server is not responding. Check the URL and try again.';
        });
        return;
      }
      
      // Save config
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('server_url', url);
      await prefs.setString('api_key', key);
      
      if (mounted) {
        context.go('/projects');
      }
    } catch (e) {
      setState(() {
        _isChecking = false;
        _errorMessage = 'Connection failed: ${e.toString()}';
      });
    }
  }
}
```

---

### Task 2.5 — Projects Screen

**File:** `lib/features/projects/projects_screen.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/providers/projects_provider.dart';
import 'add_project_sheet.dart';
import 'project_card.dart';

class ProjectsScreen extends ConsumerWidget {
  const ProjectsScreen({super.key});
  
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final projectsAsync = ref.watch(projectsProvider);
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Repositories'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(projectsProvider),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => context.push('/setup'),
          ),
        ],
      ),
      body: projectsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 16),
              Text('Failed to load repositories', 
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text(error.toString(), textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.grey, fontSize: 13)),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: () => ref.invalidate(projectsProvider),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (projects) {
          if (projects.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.folder_open, size: 64, color: Colors.grey),
                  const SizedBox(height: 16),
                  const Text('No repositories indexed yet'),
                  const SizedBox(height: 8),
                  const Text(
                    'Add a repository using the + button',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 24),
                  FilledButton.icon(
                    onPressed: () => _showAddSheet(context, ref),
                    icon: const Icon(Icons.add),
                    label: const Text('Add Repository'),
                  ),
                ],
              ),
            );
          }
          
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: projects.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final project = projects[index];
              return ProjectCard(
                project: project,
                onTap: () => context.push('/projects/${project.projectId}'),
              );
            },
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showAddSheet(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('Add Repository'),
      ),
    );
  }
  
  void _showAddSheet(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => const AddProjectSheet(),
    );
  }
}
```

**File:** `lib/features/projects/project_card.dart`

```dart
import 'package:flutter/material.dart';
import '../../core/api/models/project.dart';

class ProjectCard extends StatelessWidget {
  final RIPProject project;
  final VoidCallback onTap;
  
  const ProjectCard({
    super.key,
    required this.project,
    required this.onTap,
  });
  
  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Project name and type indicator
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      Icons.account_tree,
                      size: 20,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          project.projectName,
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.bold),
                        ),
                        if (project.gitUrl != null)
                          Text(
                            project.gitUrl!.replaceFirst('https://github.com/', ''),
                            style: const TextStyle(color: Colors.grey, fontSize: 12),
                            overflow: TextOverflow.ellipsis,
                          ),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right, color: Colors.grey),
                ],
              ),
              
              const SizedBox(height: 12),
              
              // Stats row
              Row(
                children: [
                  _StatChip(
                    icon: Icons.insert_drive_file,
                    label: '${project.filesCount} files',
                  ),
                  const SizedBox(width: 8),
                  _StatChip(
                    icon: Icons.functions,
                    label: '${project.entitiesCount} entities',
                  ),
                ],
              ),
              
              if (project.languages.isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  children: project.languages.take(4).map((lang) => Chip(
                    label: Text(lang, style: const TextStyle(fontSize: 11)),
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    padding: EdgeInsets.zero,
                    labelPadding: const EdgeInsets.symmetric(horizontal: 8),
                    visualDensity: VisualDensity.compact,
                  )).toList(),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final IconData icon;
  final String label;
  
  const _StatChip({required this.icon, required this.label});
  
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: Colors.grey),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 13)),
      ],
    );
  }
}
```

---

### Task 2.6 — Add Repository Sheet with WebSocket Progress

**File:** `lib/features/projects/add_project_sheet.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:convert';
import '../../core/providers/projects_provider.dart';

class AddProjectSheet extends ConsumerStatefulWidget {
  const AddProjectSheet({super.key});
  
  @override
  ConsumerState<AddProjectSheet> createState() => _AddProjectSheetState();
}

class _AddProjectSheetState extends ConsumerState<AddProjectSheet> {
  final _urlController = TextEditingController();
  final _nameController = TextEditingController();
  final _branchController = TextEditingController(text: 'main');
  
  bool _isIndexing = false;
  String? _jobId;
  String _progressMessage = '';
  String _progressStatus = '';
  int _filesIndexed = 0;
  int _entitiesFound = 0;
  
  WebSocketChannel? _wsChannel;
  
  @override
  void dispose() {
    _wsChannel?.sink.close();
    _urlController.dispose();
    _nameController.dispose();
    _branchController.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        24, 24, 24,
        MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Handle bar
          Center(
            child: Container(
              width: 40, height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 20),
          
          Text(
            'Add Repository',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 4),
          const Text(
            'Enter a Git URL to index a new repository',
            style: TextStyle(color: Colors.grey),
          ),
          
          const SizedBox(height: 24),
          
          if (!_isIndexing) ...[
            TextField(
              controller: _urlController,
              decoration: const InputDecoration(
                labelText: 'Git URL',
                hintText: 'https://github.com/user/repo',
                prefixIcon: Icon(Icons.link),
                border: OutlineInputBorder(),
              ),
              onChanged: (url) {
                // Auto-extract project name from URL
                final parts = url.split('/');
                if (parts.length >= 2) {
                  final repoName = parts.last
                      .replaceAll('.git', '')
                      .replaceAll('-', ' ')
                      .replaceAll('_', ' ');
                  if (repoName.isNotEmpty) {
                    _nameController.text = repoName;
                  }
                }
              },
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _nameController,
              decoration: const InputDecoration(
                labelText: 'Project Name',
                prefixIcon: Icon(Icons.folder),
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _branchController,
              decoration: const InputDecoration(
                labelText: 'Branch',
                prefixIcon: Icon(Icons.merge_type),
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _startIndexing,
                icon: const Icon(Icons.cloud_download),
                label: const Text('Start Indexing'),
              ),
            ),
          ] else ...[
            // Progress display
            _buildProgressDisplay(),
          ],
        ],
      ),
    );
  }
  
  Widget _buildProgressDisplay() {
    final isComplete = _progressStatus == 'complete';
    final isFailed = _progressStatus == 'failed';
    
    return Column(
      children: [
        // Status icon
        Container(
          width: 64, height: 64,
          decoration: BoxDecoration(
            color: isComplete
                ? Colors.green.shade50
                : isFailed
                    ? Colors.red.shade50
                    : Theme.of(context).colorScheme.primaryContainer,
            shape: BoxShape.circle,
          ),
          child: isComplete
              ? const Icon(Icons.check_circle, color: Colors.green, size: 32)
              : isFailed
                  ? const Icon(Icons.error, color: Colors.red, size: 32)
                  : SizedBox(
                      width: 32, height: 32,
                      child: CircularProgressIndicator(
                        strokeWidth: 3,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
        ),
        
        const SizedBox(height: 16),
        
        Text(
          isComplete ? 'Indexing Complete!' : 
          isFailed ? 'Indexing Failed' : 'Indexing Repository...',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        
        const SizedBox(height: 8),
        
        Text(
          _progressMessage,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: isFailed ? Colors.red : Colors.grey,
            fontSize: 13,
          ),
        ),
        
        if (!isComplete && !isFailed) ...[
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _ProgressStat(
                icon: Icons.insert_drive_file,
                label: 'Files',
                value: '$_filesIndexed',
              ),
              const SizedBox(width: 24),
              _ProgressStat(
                icon: Icons.functions,
                label: 'Entities',
                value: '$_entitiesFound',
              ),
            ],
          ),
        ],
        
        const SizedBox(height: 24),
        
        if (isComplete) ...[
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () {
                ref.invalidate(projectsProvider);
                Navigator.of(context).pop();
              },
              child: const Text('View Repository'),
            ),
          ),
        ] else if (isFailed) ...[
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close'),
            ),
          ),
        ],
      ],
    );
  }
  
  Future<void> _startIndexing() async {
    final client = ref.read(ripClientProvider);
    
    try {
      final job = await client.startGitIndex(
        gitUrl: _urlController.text.trim(),
        projectName: _nameController.text.trim(),
        branch: _branchController.text.trim(),
      );
      
      setState(() {
        _isIndexing = true;
        _jobId = job.jobId;
        _progressMessage = 'Starting...';
        _progressStatus = 'pending';
      });
      
      // Connect to WebSocket for real-time progress
      _connectWebSocket(job.jobId);
      
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to start indexing: $e')),
      );
    }
  }
  
  void _connectWebSocket(String jobId) {
    final serverUrl = ref.read(serverUrlProvider);
    final wsUrl = serverUrl
        .replaceFirst('http://', 'ws://')
        .replaceFirst('https://', 'wss://');
    
    _wsChannel = WebSocketChannel.connect(
      Uri.parse('$wsUrl/ws/index/$jobId'),
    );
    
    _wsChannel!.stream.listen(
      (message) {
        final data = json.decode(message as String) as Map<String, dynamic>;
        setState(() {
          _progressStatus = data['status'] as String? ?? '';
          _progressMessage = data['message'] as String? ?? '';
          _filesIndexed = data['files_indexed'] as int? ?? 0;
          _entitiesFound = data['entities_found'] as int? ?? 0;
        });
      },
      onDone: () {
        // WebSocket closed — check final status
        if (_progressStatus != 'complete' && _progressStatus != 'failed') {
          setState(() {
            _progressStatus = 'complete';
            _progressMessage = 'Indexing complete';
          });
        }
      },
      onError: (error) {
        setState(() {
          _progressStatus = 'failed';
          _progressMessage = 'Connection error: $error';
        });
      },
    );
  }
}

class _ProgressStat extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  
  const _ProgressStat({
    required this.icon,
    required this.label,
    required this.value,
  });
  
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, size: 20, color: Colors.grey),
        const SizedBox(height: 4),
        Text(
          value,
          style: Theme.of(context).textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12)),
      ],
    );
  }
}
```

---

### Task 2.7 — Search Screen

**File:** `lib/features/search/search_screen.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/providers/projects_provider.dart';

class SearchScreen extends ConsumerStatefulWidget {
  final String projectId;
  final String projectName;
  
  const SearchScreen({
    super.key,
    required this.projectId,
    required this.projectName,
  });
  
  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _searchController = TextEditingController();
  List<dynamic> _results = [];
  bool _isSearching = false;
  String? _lastQuery;
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Search ${widget.projectName}'),
      ),
      body: Column(
        children: [
          // Search bar
          Padding(
            padding: const EdgeInsets.all(16),
            child: SearchBar(
              controller: _searchController,
              hintText: 'Search by meaning, not keywords...',
              leading: const Icon(Icons.search),
              trailing: [
                if (_isSearching)
                  const SizedBox(
                    width: 20, height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
              onSubmitted: _search,
            ),
          ),
          
          // Quick search chips
          if (_lastQuery == null) ...[
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Wrap(
                spacing: 8,
                children: [
                  'authentication',
                  'error handling',
                  'database',
                  'retry logic',
                  'API routes',
                ].map((query) => FilterChip(
                  label: Text(query),
                  onSelected: (_) {
                    _searchController.text = query;
                    _search(query);
                  },
                )).toList(),
              ),
            ),
          ],
          
          // Results
          Expanded(
            child: _results.isEmpty
                ? _buildEmptyState()
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _results.length,
                    separatorBuilder: (_, __) => const Divider(),
                    itemBuilder: (context, index) {
                      final result = _results[index];
                      return _SearchResultTile(result: result);
                    },
                  ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildEmptyState() {
    if (_lastQuery != null) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, size: 48, color: Colors.grey),
            SizedBox(height: 16),
            Text('No results found'),
            Text('Try different keywords', 
                style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.manage_search, size: 48, color: Colors.grey),
          SizedBox(height: 16),
          Text('Search by meaning'),
          SizedBox(height: 8),
          Text(
            'Find code by what it does,\nnot just what it is named',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey),
          ),
        ],
      ),
    );
  }
  
  Future<void> _search(String query) async {
    if (query.isEmpty) return;
    
    setState(() {
      _isSearching = true;
      _lastQuery = query;
    });
    
    try {
      final client = ref.read(ripClientProvider);
      final results = await client.search(
        projectId: widget.projectId,
        query: query,
        limit: 15,
      );
      
      setState(() {
        _results = results;
        _isSearching = false;
      });
    } catch (e) {
      setState(() => _isSearching = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Search failed: $e')),
        );
      }
    }
  }
}

class _SearchResultTile extends StatelessWidget {
  final dynamic result;
  
  const _SearchResultTile({required this.result});
  
  @override
  Widget build(BuildContext context) {
    final name = result['name'] as String? ?? 'Unknown';
    final filePath = result['file_path'] as String? ?? '';
    final entityType = result['entity_type'] as String? ?? 'function';
    final score = (result['score'] as num?)?.toDouble() ?? 0.0;
    final code = result['raw_code'] as String?;
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            // Entity type icon
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: _typeColor(entityType).withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: _typeColor(entityType).withOpacity(0.3)),
              ),
              child: Text(
                entityType,
                style: TextStyle(
                  color: _typeColor(entityType),
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                name,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
            // Relevance score
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.green.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                '${(score * 100).round()}%',
                style: const TextStyle(
                  color: Colors.green,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          filePath,
          style: const TextStyle(color: Colors.grey, fontSize: 12),
        ),
        if (code != null && code.isNotEmpty) ...[
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey.shade900,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              code.length > 300 ? '${code.substring(0, 300)}...' : code,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ],
    );
  }
  
  Color _typeColor(String type) {
    switch (type) {
      case 'class': return Colors.blue;
      case 'function': return Colors.green;
      case 'method': return Colors.teal;
      case 'widget': return Colors.purple;
      case 'module': return Colors.orange;
      default: return Colors.grey;
    }
  }
}
```

---

### Task 2.8 — App Navigation and Main

**File:** `lib/shared/navigation/app_router.dart`

```dart
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../features/setup/setup_screen.dart';
import '../../features/projects/projects_screen.dart';
import '../../features/search/search_screen.dart';

final appRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/setup',
    redirect: (context, state) async {
      final prefs = await SharedPreferences.getInstance();
      final serverUrl = prefs.getString('server_url');
      
      if (serverUrl == null && state.matchedLocation != '/setup') {
        return '/setup';
      }
      if (serverUrl != null && state.matchedLocation == '/setup') {
        return '/projects';
      }
      return null;
    },
    routes: [
      GoRoute(
        path: '/setup',
        builder: (_, __) => const SetupScreen(),
      ),
      GoRoute(
        path: '/projects',
        builder: (_, __) => const ProjectsScreen(),
        routes: [
          GoRoute(
            path: ':projectId',
            builder: (_, state) {
              final projectId = state.pathParameters['projectId']!;
              return ProjectDetailScreen(projectId: projectId);
            },
            routes: [
              GoRoute(
                path: 'search',
                builder: (_, state) {
                  final projectId = state.pathParameters['projectId']!;
                  final name = state.uri.queryParameters['name'] ?? '';
                  return SearchScreen(
                    projectId: projectId,
                    projectName: name,
                  );
                },
              ),
            ],
          ),
        ],
      ),
    ],
  );
});
```

**File:** `lib/main.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'shared/navigation/app_router.dart';
import 'core/config/theme.dart';

void main() {
  runApp(const ProviderScope(child: RIPApp()));
}

class RIPApp extends ConsumerWidget {
  const RIPApp({super.key});
  
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    
    return MaterialApp.router(
      title: 'RIP — Repository Intelligence',
      theme: ripLightTheme,
      darkTheme: ripDarkTheme,
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
```

---

### Task 2.9 — Phase 2 Verification

```bash
# In the rip_app directory:

# 1. Get dependencies
flutter pub get

# 2. Check for issues
flutter analyze

# 3. Run tests
flutter test

# 4. Build for Android debug
flutter build apk --debug

# 5. Run on connected device (or emulator)
flutter run

# 6. Verify these flows work end-to-end:
# a. Open app → shows Setup screen
# b. Enter server URL → connects → goes to Projects screen
# c. Projects screen → shows list from API
# d. Tap + → shows Add Repository sheet
# e. Enter Git URL → starts indexing → shows WebSocket progress
# f. Progress completes → project appears in list
# g. Tap project → can search, trace, view architecture
```

---

## PHASE 1 COMPLETE CHECKLIST

```
□ core/git/cloner.py — GitCloneService implemented and tested
□ server/routers/git.py — /git/index and /git/status/{job_id} endpoints
□ server/routers/projects.py — /projects/ CRUD endpoints  
□ server/routers/ws.py — WebSocket progress endpoint
□ server/middleware/auth.py — API key authentication
□ All existing routers updated with project_id param
□ Project ORM model updated with git_url, files_count, entities_count, languages
□ Alembic migration run successfully
□ Two different repos indexed and queries return different results
□ API key auth blocks unauthorized requests
□ uv run ruff check . — clean
□ uv run pytest tests/ — passing
```

## PHASE 2 COMPLETE CHECKLIST

```
□ flutter pub get — no errors
□ flutter analyze — no errors
□ RIPClient connects to Phase 1 server
□ Setup screen saves and restores server config
□ Projects screen shows all indexed repositories
□ Add Repository sheet shows WebSocket real-time progress
□ Search screen returns semantic results
□ flutter build apk --debug — produces APK
□ App runs on device/emulator end-to-end
```

---

## WHAT NOT TO BUILD IN THESE PHASES

Skip everything below. These are valid future features but not part of Phase 1 or 2.

- Offline mode or local caching of indexed data
- User accounts or multi-user authentication  
- Push notifications for indexing completion
- Repository comparison between projects
- Code editor or inline editing from the app
- CI/CD webhook triggers for automatic re-indexing
- Billing or usage limits
- The Context Gateway integration (gateway is already built; integration comes later)
- Android-specific features like file picker or share sheet
- iOS build configuration (focus on Android first)
