# RIP Setup Guide

This guide covers setting up RIP in both server mode and local mode.

---

## 📋 Prerequisites

### For Both Modes:
- Python 3.11+
- `uv` package manager (recommended)

### For Server Mode Only:
- Docker and Docker Compose

---

## 🏁 Quick Start (Local Mode - No Docker!)

Local mode is the easiest way to get started with RIP - no Docker required!

### Step 1: Clone the RIP repository
```bash
git clone https://github.com/pratiksingh1702/RIP.git
cd RIP
```

### Step 2: Set up the Python environment
```bash
uv sync
```

### Step 3: Initialize your first project
Navigate to the repository you want to analyze:
```bash
cd /path/to/your/repo
uv run repo init . --project-name my-awesome-project
```

### Step 4: Index your repository in local mode
```bash
uv run repo index . --mode local
```

### Step 5: Start exploring!
Try some commands:
```bash
uv run repo search "authentication"
uv run repo trace MainFunction
uv run repo explain "how does the login flow work" --no-llm --diagram
```

---

## 🚀 Full Server Mode Setup

Server mode unlocks all RIP features including Flutter app, REST API, Context Gateway, and more.

### Step 1: Clone the repository and set up environment
```bash
git clone https://github.com/pratiksingh1702/RIP.git
cd RIP
uv sync
```

### Step 2: Start Docker services
```bash
docker compose up -d
```

This starts:
- Neo4j (graph database)
- Qdrant (vector search)
- PostgreSQL (metadata store)
- Redis (cache)

### Step 3: Verify server health
```bash
uv run repo doctor
```

You should see that Neo4j, Qdrant, and PostgreSQL are healthy.

### Step 4: Initialize a project
```bash
cd /path/to/your/repo
uv run repo init . --project-name my-project
```

### Step 5: Index your repository
```bash
uv run repo index .
```

### Step 6: Start the RIP server (optional)
```bash
uv run repo serve
```

The server will start at `http://localhost:8000`.

---

## 📱 Flutter App Setup

1. Make sure server mode is running (`docker compose up -d` + `uv run repo serve`)
2. Navigate to the Flutter app directory:
   ```bash
   cd rip_app
   ```
3. Install Flutter dependencies:
   ```bash
   flutter pub get
   ```
4. Run the app:
   ```bash
   flutter run
   ```
5. On the setup screen, enter your RIP server URL (e.g., `http://10.0.2.2:8000` for Android emulator, `http://localhost:8000` for iOS simulator)

---

## 🛠️ Useful Commands

### Doctor Command
Check your runtime environment and capabilities:
```bash
uv run repo doctor
```

### List Projects
See all indexed projects:
```bash
uv run repo projects
```

### Switch Active Project
```bash
uv run repo use <project-id>
```

### Delete a Project
```bash
uv run repo delete --project <project-id> --yes
```

### Delete All RIP Data
```bash
uv run repo delete --yes
```

### Start in Server Mode Explicitly
```bash
uv run repo index . --mode server
```

---

## 📚 CLI Reference

For complete CLI documentation, see `cli.md`.
