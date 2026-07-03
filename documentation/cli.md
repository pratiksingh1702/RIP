
# RIP CLI Commands

This is a comprehensive guide to all RIP (Repository Intelligence Platform) CLI commands.

## Verbose Logs
Every CLI command accepts `-v` / `--verbose`. When enabled, RIP prints detailed runtime logs and writes the full command log to `.repo-intel/logs/<command>-YYYYMMDD-HHMMSS.log` under the command's target repository when one is provided, otherwise under the current working directory.

## Runtime Modes

Runtime-aware commands accept `--mode auto|server|local`.

- `auto`: prefer server providers when Neo4j, Qdrant, and PostgreSQL are healthy; otherwise use local providers.
- `server`: require the full Docker-backed server stack.
- `local`: use `.repo-intel/local/` for graph, search payloads, and SQLite metadata.

Useful local-mode commands:

```powershell
uv run repo doctor . --mode local
uv run repo index . --mode local
uv run repo search "payment service" --mode local
uv run repo trace PaymentService --mode local
uv run repo explain PaymentService --mode local --no-llm --tree --deps
uv run repo metrics --mode local
uv run repo onboard --mode local
uv run repo delete --mode local --yes
```

Server-only capabilities include `repo serve`, Flutter, Context Gateway, WebSockets, remote Git indexing, shared indexes, and concurrent-user access. Start them with:

```powershell
docker compose up -d
uv run repo serve --mode server
```

`repo doctor` prints selected providers, active capabilities, whether the root `.venv` is active, and the local storage path.

## Table of Contents
- [repo init](#repo-init)
- [repo index](#repo-index)
- [repo trace](#repo-trace)
- [repo impact](#repo-impact)
- [repo dependencies](#repo-dependencies)
- [repo explain](#repo-explain)
- [repo search](#repo-search)
- [repo projects](#repo-projects)
- [repo use](#repo-use)
- [repo dead-code](#repo-dead-code)
- [repo onboard](#repo-onboard)
- [repo architecture](#repo-architecture)
- [repo metrics](#repo-metrics)
- [repo serve](#repo-serve)
- [repo status](#repo-status)
- [repo delete](#repo-delete)
- [repo config](#repo-config)
- [repo api-keys](#repo-api-keys)

---

## repo init
Initialize a repository for indexing.

### Usage
```powershell
repo init [repo_path] [--project-name <name>] [--isolation|--no-isolation] [--qdrant-strategy <strategy>] [-v|--verbose]
```

### Arguments & Options
- **repo_path**: Path to the repository to initialize (default: `.` - current directory)
- **--project-name <name>**: Project name stored in `.repo-intel/config.toml`
- **--isolation / --no-isolation**: Enable or disable repository isolation filters (default: enabled)
- **--qdrant-strategy <strategy>**: Qdrant isolation strategy (`payload_filter` or `collection_per_project`; default: `payload_filter`)
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo init
repo init C:\path\to\project
repo init --project-name billing-api
repo init C:\path\to\project --project-name flutter-app --qdrant-strategy payload_filter
```

---

## repo index
Index a repository's codebase, building the knowledge graph and semantic search index.

### Usage
```powershell
repo index [repo_path] [--watch] [--incremental] [--smart] [--languages <lang1,lang2,...>] [-v|--verbose]
```

### Arguments & Options
- **repo_path**: Path to the repository to index (default: `.` - current directory)
- **--watch**: Watch files and re-index automatically when changes are detected
- **--incremental**: Index only changed files instead of full index
- **--smart**: Index only git-changed, staged, untracked, and deleted source files
- **--languages <lang1,lang2,...>**: Comma-separated list of languages to restrict indexing
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo index
repo index . -v
repo index --incremental
repo index --smart
repo index --watch
repo index C:\path\to\project --languages python,typescript
```

---

## repo trace
Trace the call graph from an entry point to show dependencies and execution paths.

### Usage
```powershell
repo trace <entry_point> [--depth <n>] [--format text|json] [--project <project_id>] [--explain] [-v|--verbose]
```

### Arguments & Options
- **entry_point**: Symbol or function name to trace
- **--depth <n>**: Depth of the call graph to trace (default: 10)
- **--format <format>**: Output format (`text` or `json`)
- **--project <project_id>**: Override the active project and trace only within that project
- **--explain**: Generate an LLM-powered explanation for the call path
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo trace PythonParser
repo trace main --depth 20 --format json
repo trace BaseParser --explain
repo trace AuthService --project 3f2f-project-id
```

---

## repo impact
Analyze which parts of the codebase will be affected by changes to a symbol or file.

### Usage
```powershell
repo impact <symbol> [--format text|json] [--project <project_id>] [-v|--verbose]
```

### Arguments & Options
- **symbol**: Symbol or file name to analyze impact for
- **--format <format>**: Output format (`text` or `json`)
- **--project <project_id>**: Override the active project and analyze only within that project
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo impact PythonParser
repo impact core/parser/base.py --format json
repo impact AuthService --project 3f2f-project-id
```

---

## repo dependencies
Show file-level dependency information for one indexed file.

### Usage
```powershell
repo dependencies <file> [--format text|json] [--project <project_id>] [--limit <n>] [-v|--verbose]
```

### Arguments & Options
- **file**: File path or file name to inspect
- **--format <format>**: Output format (`text` or `json`)
- **--project <project_id>**: Override the active project and inspect only within that project
- **--limit <n>**: Maximum rows per section (default: 25)
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo dependencies type_provider.dart
repo dependencies core/parser/base.py --format json
repo dependencies auth_service.dart --project 3f2f-project-id --limit 50
```

The text view shows files that import the target, files/packages the target imports,
contained symbols, and a compact Mermaid graph.

---

## repo explain
Generate architecture-aware explanations with visual dependency graphs, workflow diagrams, and LLM-powered context.

### Usage
```powershell
repo explain <symbol> [--level file|class|function] [--provider <llm_provider>] [--model <model_name>] [--project <project_id>] [--diagram|-d] [--tree|-t] [--deps] [--no-llm] [--max-hops <n>] [-v|--verbose]
```

### Arguments & Options
- **symbol**: What to explain (can be natural language query or symbol name)
- **--level <level>**: Context level to include (`file`, `class`, or `function`)
- **--provider <provider>**: LLM provider to use (e.g., `google`, `openrouter`, `openai`, `anthropic`, `ollama`)
- **--model <model>**: Specific LLM model to use (e.g., `gemini-2.5-flash`, `deepseek/deepseek-chat`)
- **--project <project_id>**: Override the active project and explain only with that project's context
- **--diagram, -d**: Show Mermaid flowchart diagram of workflow
- **--tree, -t**: Show Rich tree view of workflow
- **--deps**: Show Rich table of dependencies
- **--no-llm**: Skip LLM generation, show only graph analysis
- **--max-hops <n>**: Maximum hops for workflow trace (default: 8)
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
# Full explanation with LLM
repo explain "how login works"

# Show Mermaid diagram + LLM explanation
repo explain "how login works" --diagram

# Show Rich tree view
repo explain "how login works" --tree

# Show dependency table
repo explain "how login works" --deps

# Graph analysis only (no LLM) - instant!
repo explain "how login works" --no-llm --tree --deps

# All visualizations + LLM
repo explain "how login works" --diagram --tree --deps

# With specific provider/model
repo explain PythonParser --provider google --model gemini-2.5-flash
repo explain AuthService --project 3f2f-project-id --no-llm --deps
```

---

## repo search
Perform semantic search over the codebase to find relevant entities.

### Usage
```powershell
repo search <query> [--limit <n>] [--language <lang>] [--service <service>] [--entity-type <type>] [--project <project_id>] [-v|--verbose]
```

### Arguments & Options
- **query**: Semantic search query (natural language description of what you're looking for)
- **--limit <n>**: Number of results to return (default: 20)
- **--language <lang>**: Filter results to specific language
- **--service <service>**: Filter results to specific service
- **--entity-type <type>**: Filter by entity type (e.g., `function`, `class`)
- **--project <project_id>**: Override the active project and search only within that project
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo search "parser"
repo search "database queries" --language python --limit 50
repo search "login flow" --project 3f2f-project-id
```

---

## repo projects
List indexed projects known to RIP.

### Usage
```powershell
repo projects [-v|--verbose]
```

### Arguments & Options
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo projects
```

---

## repo use
Set the active project for subsequent project-scoped commands.

### Usage
```powershell
repo use <project_id> [--repo-path <path>] [-v|--verbose]
```

### Arguments & Options
- **project_id**: Project id to activate
- **--repo-path <path>**: Repository folder where `.repo-intel/active_project` should be stored (default: `.`)
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo use 3f2f-project-id
repo use 3f2f-project-id --repo-path C:\path\to\project
```

---

## repo dead-code
Identify unused functions and classes in the codebase.

### Usage
```powershell
repo dead-code [--type functions|classes|all] [--format text|json] [-v|--verbose]
```

### Arguments & Options
- **--type <type>**: Entity type to check (`functions`, `classes`, or `all` - default: `all`)
- **--format <format>**: Output format (`text` or `json`)
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo dead-code
repo dead-code --type functions --format json
```

---

## repo onboard
Generate a comprehensive onboarding guide for the repository.

### Usage
```powershell
repo onboard [--output <file>] [-v|--verbose]
```

### Arguments & Options
- **--output <file>**: Save the onboarding guide to a specific file
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo onboard
repo onboard --output onboarding.md
```

---

## repo architecture
Visualize the repository's architecture as a diagram or JSON structure.

### Usage
```powershell
repo architecture [--format mermaid|json] [-v|--verbose]
```

### Arguments & Options
- **--format <format>**: Output format (`mermaid` for diagram or `json` - default: `mermaid`)
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo architecture
repo architecture --format json
```

---

## repo metrics
Show repository metrics like complexity, coupling, risk scores, and git activity.

### Usage
```powershell
repo metrics [--module <module>] [--top-risk <n>] [-v|--verbose]
```

### Arguments & Options
- **--module <module>**: Show metrics for a specific module only
- **--top-risk <n>**: Show top N high-risk modules
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo metrics
repo metrics --module core.parser --top-risk 10
```

---

## repo serve
Start the RIP API server as a persistent process.

### Usage
```powershell
repo serve [--host <host>] [--port <port>] [--reload] [-v|--verbose]
```

### Arguments & Options
- **--host <host>**: Host to bind the server to (default: `localhost`)
- **--port <port>**: Port to bind the server to (default: `8000`)
- **--reload**: Enable auto-reload when code changes (development mode)
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo serve
repo serve --host 0.0.0.0 --port 8080
```

---

## repo status
Check the indexing status of a repository.

### Usage
```powershell
repo status [repo_path] [-v|--verbose]
```

### Arguments
- **repo_path**: Repository path to check (default: `.` - current directory)
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo status
repo status C:\path\to\project
```

---

## repo delete
Completely clear RIP indexed data from Neo4j, Qdrant, and RIP storage metadata.

### Usage
```powershell
repo delete [--project <project_id>] [--yes] [--no-neo4j] [--no-qdrant] [--no-storage] [-v|--verbose]
```

### Arguments & Options
- **--project <project_id>**: Delete only one indexed project instead of all RIP data
- **--yes / -y**: Skip the interactive confirmation prompt
- **--neo4j / --no-neo4j**: Clear or skip Neo4j graph data
- **--qdrant / --no-qdrant**: Delete or skip the Qdrant vector collection
- **--storage / --no-storage**: Reset or skip RIP metadata tables
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo delete
repo delete --yes
repo delete --project d93fcec0-9811-538a-be5c-fc5be577ec5a --yes
repo delete --yes --no-storage
```

---

## repo config
View and edit RIP configuration.

### Usage
```powershell
repo config [repo_path] [--get <key>] [--set <key=value>] [--edit] [-v|--verbose]
```

### Arguments & Options
- **repo_path**: Path to the repository (default: `.`)
- **--get <key>**: Get a specific configuration value (e.g., `llm.primary_provider`)
- **--set <key=value>**: Set a configuration value (e.g., `llm.primary_provider=openai`)
- **--edit, -e**: Open the configuration file in your default editor
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Examples
```powershell
# Show all configuration
repo config

# Get a specific value
repo config --get llm.primary_provider

# Set a value
repo config --set llm.primary_provider=openai

# Open config in editor
repo config --edit
```

---

## repo api-keys
Manage API keys for authenticating with the RIP server.

### Subcommands
- `list`: List all API keys
- `create`: Create a new API key
- `revoke`: Revoke an existing API key

### Usage - List Keys
```powershell
repo api-keys list [-v|--verbose]
```

### Usage - Create Key
```powershell
repo api-keys create <name> [--description <text>] [--expires-in <days>] [-v|--verbose]
```

### Arguments & Options - Create Key
- **name**: Human-readable name for the API key
- **--description <text>**: Optional description of the key's purpose
- **--expires-in <days>**: Optional number of days until the key expires
- **-v, --verbose**: Show detailed runtime logs

### Usage - Revoke Key
```powershell
repo api-keys revoke <api_key_id> [-v|--verbose]
```

### Arguments & Options - Revoke Key
- **api_key_id**: ID of the API key to revoke
- **-v, --verbose**: Show detailed runtime logs

### Example
```powershell
# List all keys
repo api-keys list

# Create a new key
repo api-keys create "Flutter App" --description "For mobile app" --expires-in 365

# Revoke a key
repo api-keys revoke 2
```
