"""File tree and directory browser API."""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends
from server.middleware.auth import verify_api_key

router = APIRouter(prefix="/projects", tags=["projects"])

def _build_file_tree(root: Path, max_depth: int = 3, max_files: int = 200) -> list[dict]:
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
            # Skip hidden and common ignore patterns
            if name.startswith('.') and name not in ('.env', '.gitignore'):
                continue
            if name in ('node_modules', '__pycache__', '.git', 'build', 'dist', '.dart_tool', 'vendor', 'target', '.venv'):
                continue
                
            item = {
                "name": name,
                "path": str(entry.relative_to(root)).replace('\\', '/'),
                "is_directory": entry.is_dir(),
                "size_bytes": entry.stat().st_size if entry.is_file() else 0,
            }
            
            if entry.is_dir():
                children = walk(entry, depth + 1)
                if children:
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
        if "children" in item:
            result.extend(_flatten(item["children"]))
    return result

@router.get("/{project_id}/files")
async def get_file_tree(
    project_id: str,
    path: str = Query(default="", description="Subdirectory path"),
    max_depth: int = Query(default=3, le=5),
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
