
# RIP CLI Commands

This is a comprehensive guide to all RIP (Repository Intelligence Platform) CLI commands.

## Table of Contents
- [repo init](#repo-init)
- [repo index](#repo-index)
- [repo trace](#repo-trace)
- [repo impact](#repo-impact)
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
- [repo config](#repo-config)

---

## repo init
Initialize a repository for indexing.

### Usage
```powershell
repo init [repo_path] [--project-name <name>] [--isolation|--no-isolation] [--qdrant-strategy <strategy>]
```

### Arguments & Options
- **repo_path**: Path to the repository to initialize (default: `.` - current directory)
- **--project-name <name>**: Project name stored in `.repo-intel/config.toml`
- **--isolation / --no-isolation**: Enable or disable repository isolation filters (default: enabled)
- **--qdrant-strategy <strategy>**: Qdrant isolation strategy (`payload_filter` or `collection_per_project`; default: `payload_filter`)

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
repo index [repo_path] [--watch] [--incremental] [--languages <lang1,lang2,...>] [-v|--verbose]
```

### Arguments & Options
- **repo_path**: Path to the repository to index (default: `.` - current directory)
- **--watch**: Watch files and re-index automatically when changes are detected
- **--incremental**: Index only changed files instead of full index
- **--languages <lang1,lang2,...>**: Comma-separated list of languages to restrict indexing
- **-v, --verbose**: Show detailed runtime logs and write a full log file to `.repo-intel/logs/`

### Example
```powershell
repo index
repo index . -v
repo index --incremental
repo index --watch
repo index C:\path\to\project --languages python,typescript
```

---

## repo trace
Trace the call graph from an entry point to show dependencies and execution paths.

### Usage
```powershell
repo trace <entry_point> [--depth <n>] [--format text|json] [--project <project_id>] [--explain]
```

### Arguments & Options
- **entry_point**: Symbol or function name to trace
- **--depth <n>**: Depth of the call graph to trace (default: 10)
- **--format <format>**: Output format (`text` or `json`)
- **--project <project_id>**: Override the active project and trace only within that project
- **--explain**: Generate an LLM-powered explanation for the call path

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
repo impact <symbol> [--format text|json] [--project <project_id>]
```

### Arguments & Options
- **symbol**: Symbol or file name to analyze impact for
- **--format <format>**: Output format (`text` or `json`)
- **--project <project_id>**: Override the active project and analyze only within that project

### Example
```powershell
repo impact PythonParser
repo impact core/parser/base.py --format json
repo impact AuthService --project 3f2f-project-id
```

---

## repo explain
Generate LLM-powered explanations of a symbol or file's purpose and context.

### Usage
```powershell
repo explain <symbol> [--level file|class|function] [--provider <llm_provider>] [--model <model_name>] [--project <project_id>]
```

### Arguments & Options
- **symbol**: Symbol or file to explain
- **--level <level>**: Context level to include (`file`, `class`, or `function`)
- **--provider <provider>**: LLM provider to use (e.g., `google`, `openrouter`, `openai`, `anthropic`, `ollama`)
- **--model <model>**: Specific LLM model to use (e.g., `gemini-2.5-flash`, `deepseek/deepseek-chat`)
- **--project <project_id>**: Override the active project and explain only with that project's context

### Example
```powershell
repo explain "indexing pipeline"
repo explain PythonParser --level class --provider google --model gemini-2.5-flash
repo explain AuthService --project 3f2f-project-id
```

---

## repo search
Perform semantic search over the codebase to find relevant entities.

### Usage
```powershell
repo search <query> [--limit <n>] [--language <lang>] [--service <service>] [--entity-type <type>] [--project <project_id>]
```

### Arguments & Options
- **query**: Semantic search query (natural language description of what you're looking for)
- **--limit <n>**: Number of results to return (default: 20)
- **--language <lang>**: Filter results to specific language
- **--service <service>**: Filter results to specific service
- **--entity-type <type>**: Filter by entity type (e.g., `function`, `class`)
- **--project <project_id>**: Override the active project and search only within that project

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
repo projects
```

### Example
```powershell
repo projects
```

---

## repo use
Set the active project for subsequent project-scoped commands.

### Usage
```powershell
repo use <project_id> [--repo-path <path>]
```

### Arguments & Options
- **project_id**: Project id to activate
- **--repo-path <path>**: Repository folder where `.repo-intel/active_project` should be stored (default: `.`)

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
repo dead-code [--type functions|classes|all] [--format text|json]
```

### Arguments & Options
- **--type <type>**: Entity type to check (`functions`, `classes`, or `all` - default: `all`)
- **--format <format>**: Output format (`text` or `json`)

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
repo onboard [--output <file>]
```

### Arguments & Options
- **--output <file>**: Save the onboarding guide to a specific file

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
repo architecture [--format mermaid|json]
```

### Arguments & Options
- **--format <format>**: Output format (`mermaid` for diagram or `json` - default: `mermaid`)

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
repo metrics [--module <module>] [--top-risk <n>]
```

### Arguments & Options
- **--module <module>**: Show metrics for a specific module only
- **--top-risk <n>**: Show top N high-risk modules

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
repo serve [--host <host>] [--port <port>] [--reload]
```

### Arguments & Options
- **--host <host>**: Host to bind the server to (default: `localhost`)
- **--port <port>**: Port to bind the server to (default: `8000`)
- **--reload**: Enable auto-reload when code changes (development mode)

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
repo status [repo_path]
```

### Arguments
- **repo_path**: Repository path to check (default: `.` - current directory)

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
repo delete [--project <project_id>] [--yes] [--no-neo4j] [--no-qdrant] [--no-storage]
```

### Arguments & Options
- **--project <project_id>**: Delete only one indexed project instead of all RIP data
- **--yes / -y**: Skip the interactive confirmation prompt
- **--neo4j / --no-neo4j**: Clear or skip Neo4j graph data
- **--qdrant / --no-qdrant**: Delete or skip the Qdrant vector collection
- **--storage / --no-storage**: Reset or skip RIP metadata tables

### Example
```powershell
repo delete
repo delete --yes
repo delete --project d93fcec0-9811-538a-be5c-fc5be577ec5a --yes
repo delete --yes --no-storage
```

---

## repo config
Show or modify configuration settings.

*Note: This command is not yet implemented.*
