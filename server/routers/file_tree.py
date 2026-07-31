"""File tree and directory browser API."""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends
from server.middleware.auth import verify_api_key

router = APIRouter(prefix="/projects", tags=["projects"])

def _build_file_tree(root: Path, max_depth: int = 10, max_files: int = 2000) -> list[dict]:
    """Build a tree structure of the project directory."""
    tree = []
    count = 0
    
    def walk(dir_path: Path, depth: int = 0) -> list[dict]:
        nonlocal count
        if depth > max_depth or count >= max_files:
            return []
        
        items = []
        try:
            entries = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except (PermissionError, OSError):
            return items
        
        for entry in entries:
            if count >= max_files:
                break
            name = entry.name
            # Skip hidden internal system folders, but allow dot config/git files
            if name in ('.git', 'node_modules', '__pycache__', 'build', 'dist', '.dart_tool', 'vendor', 'target', '.venv', '.idea', '.vscode'):
                continue
            if name.startswith('.') and name not in ('.gitignore', '.gitattributes', '.github', '.env', '.env.example', '.gitmodules'):
                continue
                
            item = {
                "name": name,
                "path": str(entry.relative_to(root)).replace('\\', '/'),
                "is_directory": entry.is_dir(),
                "size_bytes": entry.stat().st_size if entry.is_file() else 0,
            }
            
            if entry.is_dir():
                children = walk(entry, depth + 1)
                item["children"] = children
                item["file_count"] = sum(1 for c in _flatten(children) if not c.get("is_directory"))
            
            items.append(item)
            count += 1
        
        return items
    
    return walk(root)

def _flatten(tree: list[dict]) -> list[dict]:
    """Flatten tree into list."""
    result = []
    for item in tree:
        result.append(item)
        if "children" in item and item["children"]:
            result.extend(_flatten(item["children"]))
    return result

@router.get("/{project_id}/files")
async def get_file_tree(
    project_id: str,
    path: str = Query(default="", description="Subdirectory path"),
    max_depth: int = Query(default=10, le=20),
    api_key = Depends(verify_api_key),
):
    """Get the file tree for a project."""
    from core.projects import get_project
    from core.storage.database import async_session_factory
    
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
    
    if not project or not project.root:
        raise HTTPException(status_code=404, detail="Project not found or has no root path")
    
    root = Path(project.root)
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"Project root not found: {root}")
    
    target = root / path if path else root
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    
    tree = _build_file_tree(target, max_depth=max_depth)
    
    return {
        "project_id": project_id,
        "project_name": project.name,
        "root": str(root),
        "current_path": path or "/",
        "files_count": project.files_count,
        "entities_count": project.entities_count,
        "tree": tree,
        "total_items": len(_flatten(tree)),
    }


@router.get("/{project_id}/files/flat")
async def get_flat_file_list(
    project_id: str,
    path: str = Query(default=""),
    pattern: str = Query(default="*"),
    api_key = Depends(verify_api_key),
):
    """Get a flat list of files matching a pattern."""
    import fnmatch
    from core.projects import get_project
    from core.storage.database import async_session_factory
    
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
    
    if not project or not project.root:
        raise HTTPException(status_code=404, detail="Project not found")
    
    root = Path(project.root)
    target = root / path if path else root
    
    files = []
    for file_path in target.rglob(pattern):
        if file_path.is_file():
            rel = str(file_path.relative_to(root)).replace('\\', '/')
            if any(skip in rel for skip in ('node_modules/', '__pycache__/', '.git/', '.dart_tool/', 'build/', 'vendor/')):
                continue
            files.append({
                "name": file_path.name,
                "path": rel,
                "size_bytes": file_path.stat().st_size,
                "extension": file_path.suffix,
            })
    
    return {
        "project_id": project_id,
        "project_name": project.name,
        "pattern": pattern,
        "files": sorted(files, key=lambda f: f["path"])[:500],
        "total": len(files),
    }


@router.get("/{project_id}/file-content")
async def get_file_content(
    project_id: str,
    path: str = Query(..., description="Relative file path"),
    api_key = Depends(verify_api_key),
):
    """Read and return content of a specific file inside project root."""
    import base64
    from core.projects import get_project
    from core.storage.database import async_session_factory
    
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
    
    if not project or not project.root:
        raise HTTPException(status_code=404, detail="Project not found or has no root path")
    
    root = Path(project.root).resolve()
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"Project root not found: {root}")
    
    target = (root / path).resolve()
    # Security: Directory traversal prevention
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=403, detail="Access denied: Path outside project root")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    
    size_bytes = target.stat().st_size
    suffix = target.suffix.lower()
    
    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp"}
    binary_exts = {".pdf", ".zip", ".gz", ".tar", ".exe", ".dll", ".so", ".dylib", ".db", ".sqlite", ".bin", ".iso", ".7z", ".pyc"}
    
    if suffix in image_exts:
        try:
            raw_bytes = target.read_bytes()
            encoded = base64.b64encode(raw_bytes).decode("ascii")
            mime_sub = suffix.lstrip(".")
            if mime_sub == "jpg":
                mime_sub = "jpeg"
            elif mime_sub == "svg":
                mime_sub = "svg+xml"
            return {
                "project_id": project_id,
                "path": path,
                "name": target.name,
                "type": "image",
                "extension": suffix,
                "size_bytes": size_bytes,
                "mime_type": f"image/{mime_sub}",
                "content_base64": encoded,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read image file: {e}")
            
    if suffix in binary_exts or size_bytes > 5 * 1024 * 1024:  # > 5MB cap
        return {
            "project_id": project_id,
            "path": path,
            "name": target.name,
            "type": "binary",
            "extension": suffix,
            "size_bytes": size_bytes,
        }
        
    # Text / Code / Config / Markdown
    try:
        raw_text = target.read_text(encoding="utf-8", errors="replace")
        lines_count = raw_text.count("\n") + (1 if raw_text else 0)
        return {
            "project_id": project_id,
            "path": path,
            "name": target.name,
            "type": "text",
            "extension": suffix,
            "size_bytes": size_bytes,
            "lines_count": lines_count,
            "content": raw_text,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read text file: {e}")

from pydantic import BaseModel
from typing import Optional
import subprocess

class FileUpdateRequest(BaseModel):
    path: str
    content: str
    commit_message: Optional[str] = None

@router.put("/{project_id}/file-content")
async def update_file_content(
    project_id: str,
    request: FileUpdateRequest,
    api_key = Depends(verify_api_key),
):
    """Update file content and optionally commit to git."""
    from core.projects import get_project
    from core.storage.database import async_session_factory
    
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
    
    if not project or not project.root:
        raise HTTPException(status_code=404, detail="Project not found")
    
    root = Path(project.root).resolve()
    target = (root / request.path).resolve()
    
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=403, detail="Path outside project root")
    
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(request.content, encoding="utf-8")
        
        commit_status = None
        if request.commit_message:
            try:
                rel_path = str(target.relative_to(root))
                # Ensure git repo exists
                if not (root / ".git").exists():
                    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
                
                # Git add relative path
                subprocess.run(["git", "add", rel_path], cwd=str(root), check=True, capture_output=True)
                
                # Git commit respecting user's global/local git configuration
                res = subprocess.run(
                    ["git", "commit", "-m", request.commit_message],
                    cwd=str(root),
                    capture_output=True,
                    text=True
                )
                
                # If git identity is missing on system, fallback to local OS user info
                if res.returncode != 0 and ("tell me who you are" in res.stderr.lower() or "author identity unknown" in res.stderr.lower()):
                    import getpass
                    username = getpass.getuser() or "User"
                    res = subprocess.run(
                        [
                            "git",
                            "-c", f"user.name={username}",
                            "-c", f"user.email={username}@users.noreply.github.com",
                            "commit",
                            "-m", request.commit_message
                        ],
                        cwd=str(root),
                        capture_output=True,
                        text=True
                    )
                
                if res.returncode == 0:
                    commit_status = "success"
                else:
                    err = (res.stderr + res.stdout).strip()
                    commit_status = f"failed: {err if err else 'nothing to commit or no changes'}"
            except Exception as e:
                commit_status = f"failed: {e}"
        
        return {
            "success": True,
            "path": request.path,
            "size_bytes": target.stat().st_size,
            "commit_status": commit_status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update file: {e}")

