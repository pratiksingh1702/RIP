# RIP Full Audit and Complete Workflow

## Overview
RIP (Repository Intelligence Platform) is a multi-interface platform that transforms source code into a queryable knowledge graph and semantic search engine, available via:
1. **CLI**: Python-based command line interface
2. **Server (FastAPI)**: HTTP REST and WebSocket server
3. **Mobile App (Flutter)**: Android/iOS cross-platform mobile interface
4. **VS Code Extension**: IDE integration
5. **MCP Server**: Model Context Protocol for AI coding assistants
6. **Gateway**: AI orchestration layer for LLM integration

---

## 1. Repository Structure
```
RIP/
├── cli/                      # Command Line Interface
├── core/                     # Core business logic (graph, index, search, services
├── server/                   # FastAPI web server
├── gateway/                 # AI Agent orchestration layer
├── mcp/                     # MCP server
├── rip_app/                 # Flutter mobile app
├── vscode-extension/        # VSCode extension
├── web/                     # Landing page
└── tests/                  # Test suite
```

---

## 2. Mobile App (Flutter) Architecture

### 2.1. Tech Stack
- **Framework: Flutter (cross-platform Android/iOS
- **HTTP Client**: Dio for API calls
- **State Management**: Provider
- **Local Storage**: Isar database
- **WebSocket**: Custom RipWebsocketClient

### 2.2. Core Features
1. **Setup Screen**: Configure server URL and API key
2. **Project Management**: List, select, delete, switch projects
3. **Git Indexing**: Start remote git repos (with subdirectory support)
4. **Chat Interface**: Natural language queries, rich content (Mermaid diagrams, code blocks, tables
5. **Trace/Impact/Search/Explain
6. **Real-time job status updates via WebSockets

### 2.3. Key Files
- **lib/core/api/rip_client.dart: HTTP API client
- **lib/core/api/rip_websocket_client.dart: WebSocket client
- **lib/data/models/**: Data models for API responses
- **lib/presentation/providers/: State management
- **lib/presentation/screens/: Screens of the app

---

## 3. FastAPI Server Architecture

### 3.1. Server Tech Stack
- Web Framework: FastAPI
- Server Runtime: Uvicorn
- Authentication: API keys stored in PostgreSQL
- Database: 
  - PostgreSQL (via SQLAlchemy ORM)
  - Neo4j (for knowledge graph
  - Qdrant (vector search)
  - SQLite (local mode)

### 3.2. API Endpoints
All endpoints except `/health` require `verify_api_key` middleware for auth!
Here's a list of them:

| Endpoint Group | Router | Description |
|---|---|---|
| Projects | projects | Manage projects |
| Index | index | Index repositories |
| Git | git | Remote git indexing |
| Search | search | Semantic and graph search |
| Trace | trace | Call graph tracing |
| Impact | impact | Impact analysis |
| Explain | explain | Natural language explanation |
| Architecture | architecture | Generate architecture diagrams |
| Onboard | onboard | Generate onboarding documentation |
| API Keys | api_keys | Manage API keys (create/revoke |
| WebSocket | ws | Real-time job status updates |

### 3.3. Request/Response Envelope
All responses are wrapped in an envelope handled by `server.middleware.errors.envelope_errors
Example:
```json
{
  "status": "ok",
  "data": { ... }
}
```

---

## 4. Core Modules

### 4.1. Parser
Uses tree-sitter to parse source code and extract:
- Entities: files, functions, classes, widgets,
- Relationships: calls, imports, inheritance,
Supported languages: Python, TypeScript, Java, Go, Rust, Dart/Flutter.

### 4.2. Indexer
Indexes code and builds knowledge graph!
In local mode: Stores data in SQLite/NetworkX in `.repo-intel/local/
In server mode: Stores in Neo4j/Qdrant/PostgreSQL.

### 4.3. Graph (Optional Gateway: AI orchestration,
This part is not shown in `gateway/`

## 5. Local Mode vs Server Mode
| Feature | Local Mode | Server Mode |
|---|---|---|
| Docker Required | No | Yes |
| Works Offline | Yes | No |
| Storage | Local filesystem (.repo-intel/) | PostgreSQL, Neo4j, Qdrant |
| HTTP API | No | Yes |
| MCP Server | Yes | Yes |
| Mobile App | No | Yes |
| Shared Indexes | No | Yes |

---

## 6. Workflows

### 6.1. User Journey: Mobile App Setup
1. Download and open Flutter app from releases
2. Open setup screen, enter server url/api key
3. Add project from git or existing project
4. Start indexing via git repo
5. Ask questions via chat interface!
6. Get back rich responses with diagrams and code.

### 6.2. Git Indexing Flow (Mobile → Server)
```
1. Mobile calls `/git/index`,
2. Server clones repo, extracts files, parses with tree-sitter,
3. Indexes, builds,
4. Websocket sends back updates,
5. User gets updated job status.

### 6.3. Explain Query
Mobile app sends to `/explain`,
server runs core explain,
returns wrapped JSON,
mobile app renders into rich UI.
