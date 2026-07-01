#!/usr/bin/env python
import os
import sys
import subprocess
from pathlib import Path

def run_pyinstaller():
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # PyInstaller uses different separators for --add-data on Windows (;) vs Unix (:)
    sep = ";" if sys.platform.startswith("win") else ":"

    args = [
        "uv",
        "run",
        "pyinstaller",
        "--name=rip",
        "--onefile",
        "--console",  # Show console since we're a CLI tool
        "--add-data=cli" + sep + "cli",
        "--add-data=core" + sep + "core",
        "--add-data=server" + sep + "server",
        "--add-data=mcp" + sep + "mcp",
        "--add-data=gateway" + sep + "gateway",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=neo4j",
        "--hidden-import=qdrant_client",
        "--hidden-import=tree-sitter-language-pack",
        "--hidden-import=typer",
        "--hidden-import=rich",
        "cli/main.py"
    ]

    print("Building RIP with PyInstaller...")
    print(f"Using separator: '{sep}'")
    try:
        subprocess.run(args, check=True)
        print("\n✅ Build complete! Output is in 'dist/' directory!")
        print(f"Executable path: {project_root / 'dist' / ('rip.exe' if sys.platform.startswith('win') else 'rip')}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed with error code {e.returncode}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_pyinstaller()
