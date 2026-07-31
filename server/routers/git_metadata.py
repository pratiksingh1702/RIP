"""Git history, contributors, and code ownership API."""
from __future__ import annotations
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends
from server.middleware.auth import verify_api_key

router = APIRouter(prefix="/projects", tags=["projects"])

def _run_git(root: Path, args: list[str], timeout: int = 30) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""

import re
import httpx
from typing import Any

def _parse_github_owner_repo(git_url_or_remote: str) -> tuple[str, str] | None:
    if not git_url_or_remote:
        return None
    m = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", git_url_or_remote)
    if m:
        return m.group(1), m.group(2)
    return None

async def _fetch_github_commits(owner: str, repo: str, limit: int = 100) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={limit}"
    headers = {"User-Agent": "RIP-App", "Accept": "application/vnd.github+json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                raw = res.json()
                commits = []
                for item in raw:
                    c = item.get("commit", {})
                    author = c.get("author", {})
                    commits.append({
                        "hash": item.get("sha", "")[:8],
                        "full_hash": item.get("sha", ""),
                        "author": author.get("name") or (item.get("author") or {}).get("login") or "Unknown",
                        "email": author.get("email") or "",
                        "date": author.get("date") or "",
                        "message": (c.get("message") or "").split("\n")[0][:200],
                    })
                return commits
    except Exception:
        pass
    return []

async def _fetch_github_contributors(owner: str, repo: str, limit: int = 20) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors?per_page={limit}"
    headers = {"User-Agent": "RIP-App", "Accept": "application/vnd.github+json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                raw = res.json()
                contributors = []
                for item in raw:
                    contributors.append({
                        "name": item.get("login") or "Contributor",
                        "email": item.get("html_url") or "",
                        "commits": item.get("contributions", 1),
                    })
                return contributors
    except Exception:
        pass
    return []

@router.get("/{project_id}/git/history")
async def get_git_history(
    project_id: str,
    file_path: str = Query(default="", description="Filter by file path"),
    limit: int = Query(default=100, le=1000),
    api_key = Depends(verify_api_key),
):
    """Get git commit history for a project or specific file."""
    from core.projects import get_project
    from core.storage.database import async_session_factory
    
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
    
    if not project or not project.root:
        raise HTTPException(status_code=404, detail="Project not found")
    
    root = Path(project.root)
    
    # Try to find git root
    git_root = root
    while git_root != git_root.parent:
        if (git_root / ".git").exists():
            break
        git_root = git_root.parent
    
    commits = []
    if (git_root / ".git").exists():
        args = ["log", f"--max-count={limit}", "--format=%H|%an|%ae|%ai|%s"]
        if file_path:
            args.extend(["--", file_path])
        
        output = _run_git(git_root, args)
        if output:
            for line in output.split('\n'):
                if not line.strip():
                    continue
                parts = line.split('|', 4)
                if len(parts) >= 5:
                    commits.append({
                        "hash": parts[0][:8],
                        "full_hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4][:200],
                    })

    # If local git returns <= 1 commit (e.g. shallow clone), check GitHub API
    if len(commits) <= 1:
        gh_info = None
        if hasattr(project, "git_url") and project.git_url:
            gh_info = _parse_github_owner_repo(project.git_url)
        if not gh_info and (git_root / ".git").exists():
            remote = _run_git(git_root, ["config", "--get", "remote.origin.url"])
            gh_info = _parse_github_owner_repo(remote)
        
        if gh_info:
            gh_commits = await _fetch_github_commits(gh_info[0], gh_info[1], limit=limit)
            if gh_commits:
                commits = gh_commits

    return {
        "project_id": project_id,
        "project_name": project.name,
        "git_root": str(git_root),
        "commits": commits,
        "total": len(commits),
    }


@router.get("/{project_id}/git/contributors")
async def get_contributors(
    project_id: str,
    limit: int = Query(default=20, le=100),
    api_key = Depends(verify_api_key),
):
    """Get top contributors with commit counts."""
    from core.projects import get_project
    from core.storage.database import async_session_factory
    
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
    
    if not project or not project.root:
        raise HTTPException(status_code=404, detail="Project not found")
    
    root = Path(project.root)
    git_root = root
    while git_root != git_root.parent:
        if (git_root / ".git").exists():
            break
        git_root = git_root.parent
    
    contributors = []
    if (git_root / ".git").exists():
        output = _run_git(git_root, ["shortlog", "-sne", "--all"])
        if output:
            for line in output.split('\n')[:limit]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('\t', 1)
                if len(parts) == 2:
                    try:
                        count = int(parts[0].strip())
                        name_email = parts[1].strip()
                        name = name_email.split('<')[0].strip() if '<' in name_email else name_email
                        email = name_email.split('<')[1].rstrip('>') if '<' in name_email else ''
                        contributors.append({
                            "name": name,
                            "email": email,
                            "commits": count,
                        })
                    except ValueError:
                        continue

    # If local git returns <= 1 contributor, check GitHub API
    if len(contributors) <= 1:
        gh_info = None
        if hasattr(project, "git_url") and project.git_url:
            gh_info = _parse_github_owner_repo(project.git_url)
        if not gh_info and (git_root / ".git").exists():
            remote = _run_git(git_root, ["config", "--get", "remote.origin.url"])
            gh_info = _parse_github_owner_repo(remote)
        
        if gh_info:
            gh_contribs = await _fetch_github_contributors(gh_info[0], gh_info[1], limit=limit)
            if gh_contribs:
                contributors = gh_contribs

    return {
        "project_id": project_id,
        "contributors": contributors,
        "total": len(contributors),
    }


@router.get("/{project_id}/git/churn")
async def get_code_churn(
    project_id: str,
    limit: int = Query(default=20, le=50),
    api_key = Depends(verify_api_key),
):
    """Get files with the most changes (code churn)."""
    from core.projects import get_project
    from core.storage.database import async_session_factory
    
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
    
    if not project or not project.root:
        raise HTTPException(status_code=404, detail="Project not found")
    
    root = Path(project.root)
    git_root = root
    while git_root != git_root.parent:
        if (git_root / ".git").exists():
            break
        git_root = git_root.parent
    
    if not (git_root / ".git").exists():
        return {"project_id": project_id, "files": [], "note": "No git repository found"}
    
    output = _run_git(git_root, ["log", "--format=format:", "--name-only", f"--max-count=200"], timeout=60)
    if not output:
        return {"project_id": project_id, "files": []}
    
    from collections import Counter
    file_counts = Counter()
    for line in output.split('\n'):
        line = line.strip()
        if line and not line.startswith('.git/') and 'node_modules' not in line:
            file_counts[line.replace('\\', '/')] += 1
    
    churn = [
        {"file_path": path, "changes": count}
        for path, count in file_counts.most_common(limit)
    ]
    
    return {
        "project_id": project_id,
        "files": churn,
        "total_unique_files": len(file_counts),
    }


@router.get("/{project_id}/git/ownership")
async def get_code_ownership(
    project_id: str,
    file_path: str = Query(default="", description="Specific file to check"),
    limit: int = Query(default=30, le=100),
    api_key = Depends(verify_api_key),
):
    """Get code ownership — who wrote each file."""
    from core.projects import get_project
    from core.storage.database import async_session_factory
    from collections import defaultdict
    
    async with async_session_factory() as session:
        project = await get_project(session, project_id)
    
    if not project or not project.root:
        raise HTTPException(status_code=404, detail="Project not found")
    
    root = Path(project.root)
    git_root = root
    while git_root != git_root.parent:
        if (git_root / ".git").exists():
            break
        git_root = git_root.parent
    
    if not (git_root / ".git").exists():
        return {"project_id": project_id, "ownership": [], "note": "No git repository found"}
    
    if file_path:
        # Get ownership for a specific file
        output = _run_git(git_root, ["shortlog", "-sne", "--", file_path])
        contributors = []
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) == 2:
                try:
                    count = int(parts[0].strip())
                    name = parts[1].split('<')[0].strip()
                    contributors.append({"name": name, "commits": count})
                except ValueError:
                    continue
        return {
            "project_id": project_id,
            "file_path": file_path,
            "contributors": contributors,
        }
    
    # Get ownership for all files
    output = _run_git(git_root, ["log", "--format=%an|%ae", "--name-only", f"--max-count=500"], timeout=60)
    if not output:
        return {"project_id": project_id, "ownership": []}
    
    file_authors = defaultdict(lambda: defaultdict(int))
    current_author = ""
    
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue
        if '|' in line and '@' in line:
            parts = line.split('|', 1)
            current_author = parts[0].strip()
        elif current_author and not line.startswith('.git/'):
            file_authors[line.replace('\\', '/')][current_author] += 1
    
    ownership = []
    for file_path, authors in sorted(file_authors.items()):
        primary = max(authors, key=authors.get)
        ownership.append({
            "file_path": file_path,
            "primary_owner": primary,
            "owner_commits": authors[primary],
            "total_commits": sum(authors.values()),
            "all_contributors": list(authors.keys()),
        })
    
    return {
        "project_id": project_id,
        "ownership": ownership[:limit],
        "total_files_tracked": len(ownership),
    }
