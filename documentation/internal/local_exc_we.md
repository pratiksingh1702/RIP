# RIP One-Click Install & Local Mode Detailed Requirements

## Table of Contents
1. [User Journey](#1-user-journey)
2. [Standalone Executable Requirements](#2-standalone-executable-requirements)
3. [Installer Features](#3-installer-features)
4. [Website Integration](#4-website-integration)
5. [Local Mode Behavior](#5-local-mode-behavior)
6. [Testing Plan](#6-testing-plan)


## 1. User Journey
The complete flow from website to first `repo index`

### Step 1: Website Visit
- User navigates to `ripdev.netlify.app`
- Website auto-detects user's OS (Windows/macOS/Linux)
- Prominent "Download RIP for [OS]" button

### Step 2: Download & Install
- User downloads platform-specific installer
- Double-click to run
- Simple wizard with:
  - License agreement (optional)
  - Install location (default: `C:\Program Files\RIP` or similar)
  - Optional: Add to PATH (checked by default)
  - Optional: Create desktop and Start menu shortcuts (checked by default)
  - Install progress indicator

### Step 3: First Use
- User opens Command Prompt/Terminal
- `repo --help` works immediately
- Navigate to their code repository:
  ```bash
  cd path/to/my/project
  repo init --project-name "My Awesome Project"
  repo index
  ```
- RIP uses **local mode** by default (no Docker!)


## 2. Standalone Executable Requirements

### Core Requirements
- **Single-file executable** (or self-contained bundle)
- **No external dependencies**:
  - No Python installation needed
  - No uv installation needed
  - No Docker installation needed
- **Small footprint**: ~100-200MB (including bundled Python and dependencies)
- **Fast startup**: <1 second for simple commands (e.g., `repo --help`)
- **Works offline**: All local mode features work without internet

### Platform-Specific Bundles
- **Windows**:
  - `.exe` installer (using Inno Setup or similar)
  - Bundled Python 3.11+
  - All RIP code and dependencies embedded
- **macOS**:
  - `.app` bundle (drag-and-drop install)
  - Notarized for macOS Gatekeeper
- **Linux**:
  - `.AppImage` (portable, no install needed)
  - Optional `.deb`/`.rpm` packages for system-wide install

### Build System
- Use `pyinstaller` via `uvx` for easy integration
- Build from the root RIP project directory
- Include:
  - All RIP code (cli/core/server/mcp/gateway)
  - All Python dependencies (sentence-transformers, tree-sitter, neo4j, qdrant, etc.)
  - ONNX model for sentence-transformers (bundled locally)
  - Tree-sitter language packs (Python, TypeScript, Java, Go, Rust, Dart)

### Exclusions from Bundle
- Server-only dependencies can be marked as optional:
  - Redis
  - Gateway-specific dependencies
- Note: Server mode still requires Docker when user wants to use REST API/Flutter/Gateway


## 3. Installer Features

### Required Features
1. **PATH Setup**:
   - Automatically add RIP install directory to user's PATH environment variable
   - No manual configuration needed
   - Works for both Windows (User PATH) and macOS/Linux (shell rc files)
2. **Shortcuts**:
   - Desktop shortcut for quick access
   - Start menu shortcuts (Windows) or Applications folder (macOS)
   - Shortcuts open a terminal with RIP ready to use
3. **Silent Install Option**:
   - Allow unattended install via command line for CI/CD or IT deployment
4. **Uninstaller**:
   - Add/Remove Programs entry (Windows)
   - Cleanly remove RIP from PATH and shortcuts
   - Optional: Keep user data (`.repo-intel` directories)

### Installer Configuration
- Default install location:
  - Windows: `C:\Program Files\RIP`
  - macOS: `/Applications/RIP`
  - Linux: `/opt/RIP`
- Installer language: English (default)


## 4. Website Integration (ripdev.netlify.app)

### Updates to web/index.html
1. **Auto OS Detection**:
   - JavaScript that detects user's operating system
   - Display corresponding download button
   - Fallback to "Download for All Platforms"
2. **Hero Section**:
   - Prominent "Download Now" button
   - OS-specific icons
3. **Getting Started Guide (1-2-3 Steps)**:
   ```
   1. Download & Install RIP
   2. Navigate to your repository
   3. Run `repo index` — done!
   ```
4. **Demo Section**:
   - Quick terminal demo showing local mode in action
   - Embed a short GIF or video
5. **Features Section**:
   - Highlight "No Docker Required" and "Offline Support"

### Hosting Installers
- Host built installers on Netlify (or your chosen hosting)
- File naming convention:
  - `rip-installer-windows-x64.exe`
  - `rip-installer-macos-universal.dmg`
  - `rip-installer-linux-x86_64.AppImage`
  - `rip-installer-linux-x86_64.deb`


## 5. Local Mode Behavior

### Default Mode
- **Auto mode is default**:
  - Checks for healthy Neo4j/Qdrant/PostgreSQL
  - If found → Server mode
  - If not found → Local mode
- User can force mode with `--mode auto|server|local`

### Local Mode Persistence
- Data stored in `.repo-intel/local/` (per project):
  - `rip.sqlite3`: SQLite metadata (projects, file hashes, embedding cache)
  - `graph.json`: Local graph data (NetworkX format)
  - `vectors.json`: Local vector index (for semantic search)

### Local Mode Limitations (with Clear Messages)
- No REST API (`repo serve` fails with: "REST API requires server mode. Run `docker compose up -d`")
- No Flutter app support
- No Context Gateway
- No remote Git indexing
- No shared indexes

### Local Mode Features
- All CLI commands:
  - `repo init`
  - `repo index`
  - `repo search`
  - `repo explain --no-llm`
  - `repo trace`
  - `repo impact`
  - `repo architecture`
  - `repo metrics`
  - `repo onboard`
  - `repo dependencies`
  - `repo dead-code`
  - `repo doctor`
  - `repo status`
  - `repo delete`
  - `repo projects`
  - `repo use`
- MCP server (local mode)
- VS Code extension (subprocess mode)


## 6. Testing Plan

### Phase 1 - Build Tests
- [ ] Build standalone executable for Windows
- [ ] Build standalone executable for macOS
- [ ] Build standalone executable for Linux
- [ ] Verify bundle size (<200MB)

### Phase 2 - Installer Tests
- [ ] Install on clean Windows machine
- [ ] Verify PATH is set up correctly
- [ ] Verify `repo --help` works in new terminal
- [ ] Uninstall and verify removal
- [ ] Repeat for macOS and Linux

### Phase 3 - Local Mode Tests
- [ ] Initialize a new project (`repo init`)
- [ ] Index a test repository (`repo index`)
- [ ] Test semantic search (`repo search "class"`)
- [ ] Test trace query (`repo trace MyClass`)
- [ ] Test impact analysis (`repo impact MyClass`)
- [ ] Verify all data is stored in `.repo-intel/local/`
- [ ] Test offline operation (disconnect internet and re-run commands)
- [ ] Test switching between local and server mode

### Phase 4 - Website Tests
- [ ] Verify OS auto-detection works on Chrome/Firefox/Safari/Edge
- [ ] Verify download links work
- [ ] Verify getting started guide is clear


## 7. Future Enhancements (Optional)
- Auto-update feature (check for updates on startup)
- GUI for RIP (instead of just CLI)
- More platform support (BSD, etc.)
