# RIP MCP Workflow Deep Dive

## Overview
RIP integrates MCP (Model Context Protocol) in two distinct ways:
1. **As a standalone MCP server** (`mcp/server.py`): For use directly in AI assistants like Claude Desktop, Cursor, etc.
2. **As a source in the Context Gateway**: For integrating external MCP servers into RIP's chat and analysis pipeline

---

## 1. RIP as an MCP Server (mcp/server.py)

### What it is
This is a **standalone MCP stdio server** that exposes all RIP CLI commands as MCP tools!

### How it works (flow diagram)
```
AI Assistant (Claude Desktop, Cursor, etc.)
    |
    | stdio: JSON-RPC requests
    ↓
mcp/server.py
    |
    | 1. Initialize session
    | 2. List tools via tools/list
    | 3. Call a tool via tools/call
    ↓
Reuses the EXACT same CLI command modules as repo command!
    |
    | Captures stdout/stderr
    ↓
Returns JSON-RPC response back to AI Assistant
```

### Key Files & Components
- **`TOOLS` dictionary (mcp/server.py:42)**: Defines all available MCP tools with JSON schemas
- **`handle_tool_call` function (mcp/server.py:287)**: Routes MCP tool calls to the correct CLI command module
- **`dispatch` function (mcp/server.py:518)**: Handles JSON-RPC request routing

### Example: How repo_explain is exposed
1. AI Assistant sends `tools/call` request with `tool_name = repo_explain` and arguments
2. `handle_tool_call` imports `cli.commands.explain` and runs it, capturing output
3. Returns output as JSON-RPC response

---

## 2. MCP Sources in Context Gateway

### What it is
This lets RIP **ingest data from external MCP servers** and combine them with RIP's own codebase analysis!

### How it works (end-to-end flow)
```
┌─────────────────────────────────────────────────────────┐
│ Mobile App or VS Code Extension                         │
├─────────────────────────────────────────────────────────┤
│ 1. User configures MCP sources in Settings             │
│ 2. Chat sends query → RIP Server's /gateway/api/context│
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ HTTP request
                    ↓
┌─────────────────────────────────────────────────────────┐
│ RIP Server (server/app.py)                              │
├─────────────────────────────────────────────────────────┤
│ Mounts Gateway routers at /gateway/*                    │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Gateway Context Router (gateway/server/routers/context.py)│
├─────────────────────────────────────────────────────────┤
│ 1. Parses task query                                   │
│ 2. Asks Planner to select sources                      │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Planner (gateway/core/planner/*)                        │
├─────────────────────────────────────────────────────────┤
│ 1. Intent classification                               │
│ 2. Domain matching                                     │
│ 3. Source selection (core + matching domain hints)     │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Executor (gateway/core/executor/engine.py)              │
├─────────────────────────────────────────────────────────┤
│ 1. Queries selected sources concurrently                │
│ 2. Circuit breaker, retries                             │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Sources (gateway/core/sources/)                          │
├─────────────────────────────────────────────────────────┤
│ • BaseSource: Abstract interface                        │
│ • RIPSource: RIP's own codebase                         │
│ • GitHubSource, JiraSource, SlackSource: Built-in       │
│ • DynamicMCPSource: Runtime-added custom MCP servers    │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ For DynamicMCPSource
                    ↓
┌─────────────────────────────────────────────────────────┐
│ External MCP Server (HTTP/SSE transport)                │
├─────────────────────────────────────────────────────────┤
│ • tools/list: Handshake                                 │
│ • tools/call: Query                                     │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ JSON-RPC response
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Ranker + Compressor (gateway/core/ranker/*)             │
├─────────────────────────────────────────────────────────┤
│ • Ranks responses by relevance                          │
│ • Compresses context to stay under token budget         │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Returns context to RIP explain/chat pipeline!           │
└─────────────────────────────────────────────────────────┘
```

---

## 3. DynamicMCPSource Deep Dive

The `DynamicMCPSource` class (`gateway/gateway/core/sources/dynamic_mcp.py`) lets you add any MCP server at runtime!

### Key Methods
| Method | What it does |
|---|---|
| `__init__` | Initializes from a `SourceRecord` (database row) |
| `query` | Sends `tools/call` JSON-RPC request to external MCP server |
| `test_connection` | Sends `tools/list` JSON-RPC request, returns one of four states: `ok`, `auth_failed`, `timeout`, `unreachable` |
| `health_check` | Wrapper around `test_connection` for executor |
| `_headers` | Builds correct Authorization/X-API-Key headers based on auth type |
| `_extract_content` | Parses MCP JSON-RPC response into plain text content |

### JSON-RPC Flow for DynamicMCPSource
```
DynamicMCPSource.query → httpx POST to external MCP server
  Payload:
  {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": query_type,
      "arguments": query_params
    }
  }
  ↓
External MCP server responds
  ↓
_extract_content parses result
  ↓
SourceResponse returned to executor
```

---

## 4. Source Registry (gateway/core/sources/registry.py)

The Source Registry maintains a list of all available sources (core, built-in, and dynamic MCP) in the database!

### SourceRecord Schema
```python
SourceRecord:
  id: str (uuid)
  name: str
  kind: str (builtin/mcp)
  transport: str (stdio/http/sse)
  endpoint_url: str | None
  auth_type: str | None
  credential: EncryptedSecret | None
  domain_hints: list[str]
  priority_hint: int
  enabled: bool
  health_status: str
  created_by: str
  created_at: datetime
```

### Key Operations
| Operation | Method |
|---|---|
| Add/Register Source | `POST /gateway/sources` → source_store.create_source → registry.refresh() |
| List Sources | `GET /gateway/sources` → source_store.list_sources |
| Update Source | `PATCH /gateway/sources/{id}` → source_store.update_source |
| Delete Source | `DELETE /gateway/sources/{id}` → source_store.delete_source |
| Test Connection | `POST /gateway/sources/{id}/test` → DynamicMCPSource.test_connection() |
| Replace Credential | `POST /gateway/sources/{id}/credential` → write-only, no reveal |

---

## 5. Mobile App Integration (Full Flow)

### Mobile App Code Flow
1. **User taps Sources in drawer** → `GatewaySourcesScreen` (rip_app/lib/presentation/screens/gateway_sources_screen.dart)
2. **Calls `ref.watch(gatewaySourcesProvider)`**
3. **GatewaySourcesProvider** calls `ripClient.gatewaySources()` → GET /gateway/sources
4. **RipClient** (rip_app/lib/core/api/rip_client.dart) fetches list of sources
5. **User taps "+ Add Source"** → show bottom sheet
6. **Selects preset or Custom MCP** → fills fields
7. **Tests connection** → POST /gateway/sources/{id}/test
8. **Saves source** → POST /gateway/sources
9. **User asks chat question** → `/explain` or `/gateway/api/context` → planner uses domain hints!

### RipClient MCP Endpoints
Check `rip_client.dart` for:
- `gatewaySources()`: GET /gateway/api/sources
- `gatewaySourcePresets()`: GET /gateway/api/sources/presets
- `createGatewaySource()`: POST /gateway/api/sources
- `updateGatewaySource()`: PATCH /gateway/api/sources/{id}
- `deleteGatewaySource()`: DELETE /gateway/api/sources/{id}
- `testGatewaySource()`: POST /gateway/api/sources/{id}/test
- `replaceGatewaySourceCredential()`: POST /gateway/api/sources/{id}/credential

---

## 6. Complete End-to-End Example: User adds Notion MCP in mobile app and queries it

### Step-by-Step Walkthrough
1. **User opens mobile app → Drawer → Settings → Sources**
2. **Taps "+ Add Source" → selects "Notion" preset**
3. **Enters endpoint URL `https://api.notion.com/mcp`, Notion token, selects domain hints: "docs", "knowledge"**
4. **Taps Test Connection** → `RipClient.testGatewaySource()` → POST `/gateway/sources/{id}/test` → runs `DynamicMCPSource.test_connection()` → sends `tools/list` to Notion MCP server → returns "ok"
5. **Taps Save** → `createGatewaySource()` → POST `/gateway/sources` → saves to `sources` database table → `registry.refresh()`
6. **User returns to chat, asks: "Show me the onboarding docs in Notion"**
7. **Planner sees domain hints "docs" and "knowledge" match query → selects RIPSource + Notion dynamic source**
8. **Executor queries both sources concurrently**
9. **Ranker + compressor combine results**
10. **User sees RIP's answer with both codebase analysis AND Notion docs!**
Okay, let's explain it with a custom, easy-to-understand example: a **Coffee Shop MCP Server**!

---

## Simple Example: Coffee Shop MCP Server

### 1. What's a custom MCP server?
It's just a tiny program that knows how to do one thing really well—in this case, answer questions about our imaginary coffee shop!

Our coffee shop MCP server will expose two tools:
- **`get_menu`**: Lists all coffee and pastries available
- **`place_order`**: Lets you order a drink/food

### 2. Step 1: Create our tiny Coffee Shop MCP Server (pseudo-code for simplicity)
```python
# tiny_coffee_mcp_server.py
import json
import sys

TOOLS = {
    "get_menu": {"description": "Show coffee shop menu"},
    "place_order": {
        "description": "Order something",
        "parameters": {"item": {"type": "string"}}
    }
}

def handle_tool_call(tool_name, args):
    if tool_name == "get_menu":
        return "☕ Lattes: $4, 🍰 Croissants: $3"
    if tool_name == "place_order":
        return f"Ordered: {args['item']}!"

for line in sys.stdin:
    request = json.loads(line.strip())
    method = request["method"]
    
    if method == "tools/list":
        print(json.dumps({"tools": TOOLS}))
    elif method == "tools/call":
        print(json.dumps({"content": handle_tool_call(...)}))
```

### 3. Step 2: Add this Coffee Shop MCP to RIP via the mobile app
1. Open RIP mobile app → **Drawer → Settings → Sources**
2. Tap **"+ Add Source" → Custom MCP**
3. Fill in the blanks:
   - **Name**: "My Coffee Shop"
   - **Endpoint URL**: `http://localhost:8765` (where our tiny server runs)
   - **Transport**: `http`
   - **Auth Type**: `none` (since our coffee shop is open to all!)
   - **Domain Hints**: Tap "food", "orders" (tells RIP when to use this source!)
4. Tap **Test Connection** (it sends a `tools/list` to our coffee shop server) → should say "ok"!
5. Tap **Save**

### 4. Step 3: Use it in RIP chat!
Go back to RIP chat and type:
> "What's on the menu at my coffee shop, and can you order a latte for me?"

### 5. What happens behind the scenes (super simple)
1. RIP Planner: "Okay, user mentioned 'menu' and 'order' → those match our coffee shop's domain hints! Let's use both RIP codebase and Coffee Shop MCP!"
2. RIP Executor: Asks both sources at the same time
3. Coffee Shop MCP responds: "☕ Lattes: $4, 🍰 Croissants: $3"
4. RIP combines responses and shows you the answer! 🎉

---

That's it! That's how MCPs work in RIP in simple words with a custom non-preset example!