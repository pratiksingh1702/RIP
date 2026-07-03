
# RIP Workflow & Complete Documentation

Welcome to **RIP (Repository Intelligence Platform)** — your comprehensive solution for turning code repositories into structured knowledge graphs, semantic indexes, and AI-ready context packages. This document covers everything you need to know as a new user, from installation to advanced usage.

---

## Table of Contents

1. [What is RIP?](#1-what-is-rip)
2. [User Journey: From Zero to Hero](#2-user-journey-from-zero-to-hero)
3. [Platform Architecture](#3-platform-architecture)
4. [Runtime Modes: Local vs Server](#4-runtime-modes-local-vs-server)
5. [Installation Interfaces](#5-installation-interfaces)
6. [Configuration & Authentication](#6-configuration--authentication)
7. [Core Workflows](#7-core-workflows)
8. [Context Gateway Deep Dive](#8-context-gateway-deep-dive)
9. [Pricing & Deployment Options](#9-pricing--deployment-options)
10. [Benefits of RIP](#10-benefits-of-rip)
11. [Troubleshooting & Support](#11-troubleshooting--support)

---

## 1. What is RIP?

RIP is a powerful platform that transforms software repositories into **queryable knowledge graphs** and **semantic indexes**. It's not just a search tool — it provides:

- **Structural understanding**: Call graphs, dependencies, inheritance, containment
- **Semantic search**: Find code by natural language description
- **Impact analysis**: Know exactly what breaks when you change something
- **Architecture visualization**: Understand your codebase at a glance
- **AI agent integration**: Provide grounded context to coding assistants
- **Multi-language support**: Python, TypeScript, Java, Go, Rust, Dart/Flutter

---

## 2. User Journey: From Zero to Hero

Let's walk through the complete journey as a new user.

### Step 1: Choose How to Install RIP

RIP offers multiple installation interfaces:

#### Option A: PyPI (Quickest for Developers)

```bash
pip install repo-intelligence==0.1.0
```

#### Option B: Standalone Installer (Zero Configuration)

1. Visit [ripdev.netlify.app](https://ripdev.netlify.app) or download from [GitHub Releases](https://github.com/your-org/rip/releases)
2. Your OS is auto-detected — download the appropriate installer
3. Run the installer (adds RIP to PATH automatically)
4. Open a new terminal and run `repo --help`

#### Option C: VS Code Extension

1. Open VS Code
2. Go to Extensions & search for "RIP"
3. Install the extension
4. Open the RIP Chat panel (Ctrl+Shift+R)

#### Option D: Flutter Mobile App

1. Download from App Store/Google Play (coming soon)
2. Open the app
3. Connect to your RIP server (local or cloud)

#### Option E: Source Code (For Contributors)

```bash
git clone https://github.com/your-org/rip.git
cd rip
uv sync
docker compose up -d
```

---

### Step 2: Initialize Your First Project

Navigate to your repository and initialize RIP:

```bash
cd path/to/your/project
repo init --project-name "My Awesome Project"
```

This creates a `.repo-intel/` directory with configuration files.

---

### Step 3: Index Your Codebase

Now build the knowledge graph and semantic index:

```bash
repo index -v
```

**What happens during indexing?**
1. RIP discovers all source files
2. Parses them using Tree-sitter for structural understanding
3. Extracts entities (files, modules, classes, functions, widgets)
4. Extracts relationships (calls, imports, contains, inherits, owns)
5. Builds a knowledge graph (Neo4j in server mode, NetworkX in local)
6. Generates semantic embeddings for each entity
7. Stores everything in your chosen runtime mode

---

### Step 4: Explore Your Codebase

You're ready! Try these commands:

```bash
# Semantic search
repo search "authentication flow"

# Trace a function's call path
repo trace UserService --depth 8

# Analyze impact of changes
repo impact UserService

# Explain how something works (with visualizations!)
repo explain "how login works" --diagram --tree --deps

# See your architecture
repo architecture

# Generate onboarding docs
repo onboard --output ONBOARDING.md
```

---

## 3. Platform Architecture

Let's look at RIP's layered architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    User Interfaces                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │   CLI    │  │FastAPI   │  │VS Code   │  │  MCP     │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│  ┌──────────┐  ┌──────────┐                            │
│  │  Flutter │  │ Gateway  │                            │
│  └──────────┘  └──────────┘                            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                      Core Engine                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Parser  │  │ Indexer  │  │  Graph   │  │  Search  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Analysis │  │   LLM    │  │ Services │            │
│  └──────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                      Storage Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Neo4j   │  │  Qdrant  │  │ Postgres │  │  Redis   │ │
│  │ (Graph)  │  │(Vectors) │  │(Metadata)│  │ (Cache)  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Runtime Modes: Local vs Server

RIP supports three runtime modes, each with different tradeoffs:

### Comparison Table

| Feature | Local Mode | Server Mode (Cloud) |
|---------|------------|---------------------|
| **Docker required?** | No | Yes |
| **Works offline?** | Yes | No |
| **Data storage** | `.repo-intel/local/` per project | Centralized databases |
| **REST API** | ❌ | ✅ |
| **Flutter app** | ❌ | ✅ |
| **Context Gateway** | ❌ | ✅ |
| **Multi-user** | ❌ | ✅ |
| **Remote Git indexing** | ❌ | ✅ |
| **Shared indexes** | ❌ | ✅ |
| **All CLI commands** | ✅ | ✅ |
| **MCP server** | ✅ | ✅ |
| **VS Code extension** | ✅ | ✅ |

### When to Use Which?

- **Local Mode**: Individual developers, quick exploration, offline work
- **Server Mode**: Teams, shared indexes, Flutter app, Context Gateway, cloud deployment

---

### Local Mode Deep Dive

**Data Storage**:
- `.repo-intel/local/rip.sqlite3` - SQLite for metadata
- `.repo-intel/local/graph.json` - NetworkX graph data
- `.repo-intel/local/vectors.json` - Semantic vectors

**How to Use Local Mode**:
```bash
# Explicitly use local mode
repo index --mode local
repo search "something" --mode local

# Or let auto mode decide (falls back to local if no Docker)
repo index
```

---

### Server Mode Deep Dive

**What You Get**:
- Persistent REST API (`repo serve`)
- Context Gateway for AI agent orchestration
- Flutter mobile app support
- Shared indexes for teams
- Remote Git repository indexing
- WebSocket support for real-time updates

**Important**: In server mode, you must configure your own environment values for Neo4j, Qdrant, PostgreSQL, Redis, and LLM providers.

**How to Start Server Mode**:
1. Configure your environment (see Section 6.2 for details)
2. Start Docker infrastructure:
   ```bash
   docker compose up -d
   ```
3. Start RIP server:
   ```bash
   uv run repo serve --host 0.0.0.0 --port 8000
   ```
4. Start Context Gateway (in another terminal):
   ```bash
   cd gateway
   uv run gateway start
   ```

---

## 5. Installation Interfaces

Let's cover each interface in detail.

### 5.1 PyPI / pip

**Best for**: Developers comfortable with Python/pip

**Installation**:
```bash
pip install repo-intelligence==0.1.0
```

**Verify**:
```bash
repo --help
```

**Configuration**: No extra config needed — works out of the box!

---

### 5.2 Standalone Installer

**Best for**: Users who want zero configuration, no Python/Docker required

**Windows**:
1. Download `rip-installer-windows-x64.exe`
2. Double-click to run
3. Follow the wizard (default options are fine)
4. Open a new Command Prompt and test: `repo --help`

**macOS**:
1. Download `rip-installer-macos-universal.dmg`
2. Open and drag RIP to Applications
3. Open Terminal and test: `repo --help`

**Linux**:
1. Download `rip-installer-linux-x86_64.AppImage`
2. Make executable: `chmod +x rip-installer-linux-x86_64.AppImage`
3. Run it

**What's Included**:
- Bundled Python 3.11+
- All RIP dependencies
- Tree-sitter language packs
- ONNX embedding model (offline capable!)

---

### 5.3 VS Code Extension

**Best for**: Developers who prefer a GUI inside their editor

**Features**:
- RIP Chat panel (right sidebar)
- Context menu actions (right-click → "Explain this", "Trace this", etc.)
- Architecture visualization
- Metrics dashboard
- Index status monitoring

**How to Use**:
1. Open any project in VS Code
2. Press Ctrl+Shift+R to open RIP Chat
3. Type commands naturally:
   - "Index this project"
   - "Explain how authentication works"
   - "Show architecture diagram"
   - "Trace UserService"

---

### 5.4 Flutter Mobile App

**Best for**: On-the-go exploration, quick code reviews

**Features**:
- Repository indexing status
- Semantic search
- Knowledge graph queries
- Project switching
- Rich chat interface

**Setup**:
1. Download from App Store/Google Play
2. On the Setup screen:
   - Enter your RIP server URL (e.g., `http://192.168.1.100:8000`)
   - Optionally enter an API key
3. Connect and start exploring!

**Accessing from Mobile**:
- Make sure your RIP server is running with `--host 0.0.0.0`
- Find your computer's IP address
- Ensure your firewall allows port 8000

---

### 5.5 Source Code

**Best for**: Contributors, developers who want to modify RIP

**Setup**:
```bash
git clone https://github.com/your-org/rip.git
cd rip
uv sync
docker compose up -d

# Verify installation
uv run repo --help
```

---

## 6. Configuration & Authentication

RIP can be configured via three methods, with this priority order:
1. **Command-line options** (highest priority)
2. **Environment variables**
3. **Configuration file** (`.repo-intel/config.toml`)

---

### 6.1 Project Isolation

RIP treats every indexed repository as a separate project with strict isolation.

```bash
# List all indexed projects
repo projects

# Switch active project
repo use &lt;project-id&gt;

# Target a specific project in any command
repo search "something" --project &lt;project-id&gt;
```

**How it works**:
- Every node in the graph carries a `project_id`
- Vector search automatically filters by project
- No cross-project leakage — perfect for monorepos or multiple repos

---

### 6.2 Server Mode & Custom URLs

In server mode, you must configure your own environment values for Neo4j, Qdrant, PostgreSQL, Redis, and LLM providers. You can customize all service URLs and credentials.

#### Configuration via `config.toml`

Edit or create `.repo-intel/config.toml`:

```toml
[graph]
neo4j_uri = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "your-password"

[search]
qdrant_host = "localhost"
qdrant_port = 6333
embedding_model = "BAAI/bge-small-en-v1.5"

[storage]
postgres_url = "postgresql+asyncpg://user:pass@localhost:5433/db"
redis_url = "redis://localhost:6379"

[server]
host = "0.0.0.0"
port = 8000
```

#### Configuration via Environment Variables

Create a `.env` file in your project root:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
QDRANT_URL=http://localhost:6333
POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5433/db
REDIS_URL=redis://localhost:6379
RIP_HOST=0.0.0.0
RIP_PORT=8000
```

#### Configuration via Command Line

For `repo serve`, you can override host and port directly:

```bash
repo serve --host 0.0.0.0 --port 8080
```

---

### 6.3 LLM Configuration

RIP supports multiple LLM providers. You can configure them via `config.toml`, environment variables, or directly via the command line.

#### Supported Providers

- Ollama (local, no API key needed)
- OpenAI
- OpenRouter
- Anthropic
- Google (Gemini)
- Groq
- Azure OpenAI

#### Configure via `config.toml`

Add this to your `.repo-intel/config.toml`:

```toml
[llm]
primary_provider = "ollama"
primary_model = "qwen2.5-coder:7b"
fallback_providers = ["openrouter", "openai", "anthropic"]
timeout = 60
max_tokens = 1500
temperature = 0.2
retry_count = 3
stream = false

# Ollama configuration
ollama_host = "http://localhost:11434"

# OpenAI configuration (uncomment and set your key)
# openai_api_key = "sk-your-key"
# openai_base_url = "https://api.openai.com/v1"

# OpenRouter configuration (uncomment and set your key)
# openrouter_api_key = "sk-or-your-key"
# openrouter_base_url = "https://openrouter.ai/api/v1"

# Anthropic configuration (uncomment and set your key)
# anthropic_api_key = "sk-ant-your-key"

# Google configuration (uncomment and set your key)
# google_api_key = "your-google-key"

# Groq configuration (uncomment and set your key)
# groq_api_key = "gsk_your_key"

# Azure OpenAI configuration (uncomment and set your keys)
# azure_api_key = "your-azure-key"
# azure_endpoint = "https://your-resource.openai.azure.com"
# azure_api_version = "2024-02-15-preview"
```

#### Configure via Environment Variables

```env
LLM_PRIMARY_PROVIDER=ollama
LLM_PRIMARY_MODEL=qwen2.5-coder:7b
OLLAMA_HOST=http://localhost:11434
OPENAI_API_KEY=sk-your-key
OPENROUTER_API_KEY=sk-or-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
GOOGLE_API_KEY=your-google-key
GROQ_API_KEY=gsk_your_key
```

#### Configure via Command Line

You can override the provider and model directly when using `repo explain`:

```bash
# Use specific provider and model
repo explain "how auth works" --provider openai --model gpt-4o

# Use --no-llm for graph-only analysis (no internet needed!)
repo explain "how auth works" --no-llm --tree --deps
```

---

### 6.4 API Key Management (Server Mode Only)

Secure your RIP server with API keys.

```bash
# Create a new API key
repo api-keys create "My Flutter App" --description "Mobile app access" --expires-in 365

# List all keys
repo api-keys list

# Revoke a key
repo api-keys revoke &lt;key-id&gt;
```

**Using API Keys**:
Include in the `Authorization` header:
```
Authorization: Bearer &lt;your-api-key&gt;
```

---

### 6.5 Config Command

Use `repo config` to view and edit your configuration:

```bash
# Show current configuration
repo config

# Set a configuration value
repo config set llm.primary_provider openai

# Get a configuration value
repo config get llm.primary_model
```

---

## 7. Core Workflows

Let's cover the most common RIP workflows.

### Workflow 1: New Developer Onboarding

Get up to speed on a new codebase in minutes:

```bash
cd new-project
repo init --project-name "New Project"
repo index -v

# See the big picture
repo architecture
repo metrics --top-risk 10

# Generate onboarding docs
repo onboard --output ONBOARDING.md
```

---

### Workflow 2: Before Making Changes

Understand the impact before you code:

```bash
# Find what you're looking for
repo search "payment processing"

# Trace the execution path
repo trace PaymentProcessor --depth 10

# See what will break
repo impact PaymentProcessor

# Understand the full context
repo explain "how payment retry works" --diagram --tree --deps
```

---

### Workflow 3: Code Review

Validate pull requests faster:

```bash
# Check the changed files
repo impact path/to/changed/file.py

# Get context on the area
repo explain "the area around this change"

# Look for dead code that can be removed
repo dead-code
```

---

### Workflow 4: AI Agent Integration (Context Gateway)

Provide grounded context to your coding assistant:

```bash
# Start the gateway
cd gateway
uv run gateway start

# Configure MCP for your AI agent
uv run gateway mcp config
```

Then your AI agent can call:
- `get_context(task="Add audit logging", token_budget=6000)`
- `validate_change(files=["auth.py"], summary="Change session expiry")`
- `search_codebase(query="password hashing")`

---

## 8. Context Gateway Deep Dive

The Context Gateway is RIP's AI orchestration layer. It:

1. **Classifies intent**: Understands what the user/agent is asking
2. **Plans retrieval**: Decides which sources to query
3. **Executes in parallel**: Gets data from RIP, GitHub, Jira, etc.
4. **Ranks & compresses**: Fits everything into a token budget
5. **Manages sessions**: Remembers context from previous interactions
6. **Checks permissions**: Ensures secure access

**Gateway Pipeline**:
```
User Task → Intent Classification → Multi-Source Planning
→ Parallel Execution → Ranking → Compression → Permissions
→ Session Memory → Context Package
```

---

## 9. Pricing & Deployment Options

### Self-Hosted (Free Forever)

**Perfect for**: Individuals, small teams, open-source projects

**What you get**:
- All local mode features
- All server mode features (if you set up Docker)
- Unlimited repositories
- Unlimited users
- Full control over your data

**Cost**: $0

---

### Cloud-Hosted (Coming Soon)

**Perfect for**: Enterprises, large teams, no DevOps overhead

**Plans**:

| Plan | Price | Features |
|------|-------|----------|
| Hobby | $19/month | 5 users, 10 repos, basic support |
| Pro | $99/month | 25 users, 100 repos, priority support |
| Enterprise | Custom | Unlimited everything, SLA, dedicated support |

**Cloud Benefits**:
- No Docker or server management
- Automatic backups
- High availability
- SSO integration
- Advanced analytics
- Dedicated support

---

## 10. Benefits of RIP

### For Individual Developers
- ⚡ **Faster onboarding**: Understand new codebases in minutes
- 🎯 **Better changes**: Know the impact before you code
- 🧠 **AI-ready context**: Give your coding assistant grounded information
- 🔌 **Works offline**: No internet needed for core features

### For Teams
- 👥 **Shared understanding**: Everyone works from the same knowledge graph
- 🚀 **Faster reviews**: Validate PRs with impact analysis
- 📊 **Architecture visibility**: Keep track of your system's design
- 🔒 **Secure**: Full control over your code and data

### For Enterprises
- 🏢 **Scalable**: Cloud-hosted option for large teams
- 🔐 **Compliant**: Self-hosted for full data control
- 📈 **Analytics**: Understand your codebase health over time
- 🤝 **Integrated**: Works with GitHub, Jira, Slack, and more

---

## 11. Troubleshooting & Support

### Common Issues

**Issue**: `repo index` is slow
**Solution**:
- Use `--smart` to index only git-changed files
- Use `--languages` to restrict to specific languages
- Check your hardware (indexing benefits from more cores)

**Issue**: Can't connect from Flutter app
**Solution**:
- Make sure server is running with `--host 0.0.0.0`
- Use your computer's actual IP (not localhost)
- Check firewall settings

**Issue**: `repo explain` says no LLM configured
**Solution**:
- Use `--no-llm` for graph-only analysis
- Configure LLM providers in `.repo-intel/config.toml`

---

### Doctor Command

Run `repo doctor` to diagnose issues:

```bash
repo doctor . --mode local
```

This checks:
- Runtime environment
- Storage providers
- Active capabilities
- Configuration status

---

### Getting Help

- **Documentation**: [ripdev.netlify.app/docs](https://ripdev.netlify.app/docs)
- **GitHub Issues**: [github.com/your-org/rip/issues](https://github.com/your-org/rip/issues)
- **Discord**: Join our community for real-time help
- **Email**: support@ripdev.net (for cloud customers)

---

## Ready to Get Started?

1. Choose your installation method from Section 5
2. Follow the user journey in Section 2
3. Explore your first repository!

Welcome to the future of code understanding — we're excited to have you on board! 🚀

---

## Appendix: Complete CLI Reference

For a full list of commands and options, see `cli.md` in the repository.

Quick reference:
- `repo init` - Initialize a project
- `repo index` - Index your codebase
- `repo search` - Semantic search
- `repo trace` - Trace call paths
- `repo impact` - Impact analysis
- `repo explain` - Explain with visualizations
- `repo dependencies` - File-level dependencies
- `repo architecture` - Architecture visualization
- `repo metrics` - Codebase metrics
- `repo onboard` - Generate onboarding docs
- `repo dead-code` - Find unused code
- `repo projects` - List projects
- `repo use` - Switch active project
- `repo serve` - Start API server
- `repo status` - Check indexing status
- `repo delete` - Clear indexed data
- `repo api-keys` - Manage API keys
- `repo doctor` - Diagnose issues

All commands accept `-v`/`--verbose` for detailed logs!
