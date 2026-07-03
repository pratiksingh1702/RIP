# VS Code Extension — Complete Chat Panel Architecture Plan

## Vision

A **single chat panel** in VS Code that behaves exactly like Copilot/Cursor/Codex — but backed by RIP's code intelligence graph instead of generic LLM knowledge. The user types queries naturally. RIP automatically selects the right command, executes it, combines results with LLM reasoning, and presents everything in a rich chat interface.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   VS Code Chat Panel                      │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  User: "How does login work?"                       │ │
│  │  ─────────────────────────────────────────────────── │ │
│  │  🤖 RIP: [auto-detected: explain flow]               │ │
│  │                                                       │ │
│  │  🌳 Workflow Tree:                                    │ │
│  │  LoginScreen → AuthProvider → AuthRepository → API    │ │
│  │                                                       │ │
│  │  📊 Mermaid Diagram:                                  │ │
│  │  ```mermaid                                           │ │
│  │  LoginScreen -->|CALLS| AuthProvider                  │ │
│  │  ```                                                  │ │
│  │                                                       │ │
│  │  📋 LLM Analysis:                                     │ │
│  │  The login flow authenticates users through...        │ │
│  │                                                       │ │
│  │  💡 Suggestions:                                      │ │
│  │  • Trace AuthProvider: `repo trace AuthProvider`      │ │
│  │  • Check impact: `repo impact AuthProvider`           │ │
│  └─────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  [Type your query...]                    [Send]      │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Chat Panel Webview (`src/panels/chatPanel.ts`)

**Purpose**: Single unified chat interface replacing all individual panels.

**Features**:
- Message history with user/AI bubbles
- Rich content rendering (Mermaid diagrams, trees, tables, code blocks)
- Streaming text responses from LLM
- Command selector dropdown (explain, search, trace, impact, architecture, metrics, auto)
- Context retention across messages in same session
- Copy, expand, and follow-up action buttons on each response

**Message Types Rendered**:
| Type | Rendering |
|------|-----------|
| `text` | Markdown with syntax highlighting |
| `tree` | Indented tree view (workflow) |
| `mermaid` | Rendered Mermaid diagram |
| `table` | Rich table (dependencies, metrics) |
| `code` | Code block with copy button |
| `suggestion` | Clickable follow-up suggestions |
| `error` | Red error banner with retry |
| `status` | Progress indicator during execution |

### 2. Intent Router (`src/intentRouter.ts`)

**Purpose**: Automatically detects what the user wants and routes to the right RIP command without requiring explicit selection.

**Intent Detection Logic**:
```typescript
interface IntentResult {
  command: 'explain' | 'search' | 'trace' | 'impact' | 'architecture' | 'metrics' | 'onboard' | 'chat';
  confidence: number;
  parameters: Record<string, any>;
  reasoning: string; // Shown in UI: "Auto-detected: explain flow"
}

function detectIntent(query: string, selectedCommand?: string): IntentResult {
  // If user explicitly selected a command, use it
  if (selectedCommand && selectedCommand !== 'auto') {
    return { command: selectedCommand, confidence: 1.0, parameters: { query } };
  }
  
  // Pattern matching for auto-detection
  const patterns = {
    explain: [/how .* work/i, /explain/i, /what is/i, /tell me about/i],
    search: [/find/i, /search/i, /where is/i, /locate/i, /look for/i],
    trace: [/trace/i, /call chain/i, /flow/i, /path from/i],
    impact: [/impact/i, /depend/i, /what breaks/i, /affect/i],
    architecture: [/architecture/i, /structure/i, /modules/i, /design/i],
    metrics: [/metrics/i, /coupling/i, /risk/i, /health/i, /churn/i],
    onboard: [/onboard/i, /overview/i, /what is this project/i, /get started/i],
  };
  
  // Score each pattern, return highest confidence match
}
```

### 3. Execution Engine (`src/executionEngine.ts`)

**Purpose**: Executes the detected command, either via CLI subprocess or HTTP API, and collects structured results.

**Two Execution Modes**:

| Mode | When Used | How |
|------|-----------|-----|
| **CLI Direct** | RIP is installed locally, `repo` command works in terminal | Spawn `uv run repo <command> <args> --json` as subprocess, parse JSON output |
| **HTTP API** | Server is running (`repo serve`), or CLI not available | POST/GET to `http://localhost:8000/<endpoint>` |

**Auto-selection logic**:
```typescript
async function executeCommand(intent: IntentResult): Promise<CommandResult> {
  // Try CLI first (no server overhead)
  if (await isCLIAvailable()) {
    return executeViaCLI(intent);
  }
  
  // Fall back to HTTP if server is running
  if (await isServerRunning()) {
    return executeViaHTTP(intent);
  }
  
  // Auto-start server and retry
  await startServer();
  return executeViaHTTP(intent);
}
```

**CLI Execution** (preferred — no server overhead):
```typescript
async function executeViaCLI(intent: IntentResult): Promise<CommandResult> {
  const args = buildCLIArgs(intent);
  const result = await spawnAsync('uv', ['run', 'repo', intent.command, ...args], {
    cwd: workspaceRoot,
    timeout: 120000,
  });
  return parseJSONOutput(result.stdout);
}
```

### 4. Response Composer (`src/responseComposer.ts`)

**Purpose**: Takes raw command output + optional LLM analysis and composes a rich chat message.

**Composition Logic**:
```typescript
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  content: MessageContent[];
  metadata: {
    command: string;
    intent: string;
    confidence: number;
    executionTime: number;
    mode: 'cli' | 'http';
  };
}

interface MessageContent {
  type: 'text' | 'tree' | 'mermaid' | 'table' | 'code' | 'suggestion' | 'error' | 'status';
  data: any;
}
```

**For `explain` results**:
```typescript
function composeExplainResponse(rawOutput: ExplainOutput): MessageContent[] {
  return [
    { type: 'text', data: rawOutput.overview },
    { type: 'tree', data: rawOutput.workflowTree },
    { type: 'mermaid', data: rawOutput.mermaidDiagram },
    { type: 'table', data: rawOutput.dependencyTable },
    { type: 'text', data: rawOutput.llmExplanation },
    { type: 'suggestion', data: rawOutput.suggestions },
  ];
}
```

### 5. Session Manager (`src/sessionManager.ts`)

**Purpose**: Maintains chat context across messages so follow-up questions understand what was previously discussed.

```typescript
interface ChatSession {
  id: string;
  repoPath: string;
  messages: ChatMessage[];
  context: {
    lastExplainedSymbol?: string;
    lastTracedSymbol?: string;
    lastSearchResults?: string[];
    activeFeature?: string;
  };
}
```

**Context-aware follow-ups**:
- User: "How does login work?" → RIP explains LoginScreen
- User: "What depends on it?" → RIP knows "it" = LoginScreen, runs impact
- User: "Show me the files" → RIP shows files from last context

### 6. Status Bar Integration (`src/statusBar.ts`)

**Purpose**: Shows RIP status in VS Code status bar.

```
🔴 RIP: Not indexed    | Click to index
🟡 RIP: Indexing... 45% | Click for details  
🟢 RIP: 2,147 entities  | Click to search
```

---

## File Structure Plan

```
vscode-extension/
├── package.json                    # Updated with new commands, mermaid dep
├── tsconfig.json
├── src/
│   ├── extension.ts                # Main activation - registers chat panel
│   ├── intentRouter.ts             # NEW: Auto-detects command from query
│   ├── executionEngine.ts          # NEW: CLI or HTTP execution
│   ├── responseComposer.ts         # NEW: Composes rich chat messages
│   ├── sessionManager.ts           # NEW: Session context management
│   ├── statusBar.ts                # NEW: Status bar indicator
│   ├── client/
│   │   ├── apiClient.ts            # UPDATED: All endpoints, health check
│   │   └── cliExecutor.ts          # NEW: CLI subprocess execution
│   ├── panels/
│   │   ├── chatPanel.ts            # NEW: Main chat panel (replaces all others)
│   │   └── chatPanelProvider.ts    # NEW: Webview provider for chat
│   ├── providers/
│   │   ├── hoverProvider.ts        # KEPT: Hover explanations
│   │   └── codeActionProvider.ts   # KEPT: Context menu actions
│   └── watchers/
│       └── fileSaveWatcher.ts      # KEPT: Auto-index on save
├── webviews/
│   └── chat/
│       ├── index.html              # Chat panel HTML
│       ├── chat.css                # Chat styling
│       └── chat.js                 # Chat logic, message rendering
└── resources/
    └── rip-icon.png                # Extension icon
```

---

## Commands to Register

| Command ID | Title | How Triggered |
|-----------|-------|---------------|
| `rip.openChat` | RIP: Open Chat | Sidebar icon, Ctrl+Shift+R |
| `rip.explain` | RIP: Explain Selected | Context menu on symbol |
| `rip.trace` | RIP: Trace Selected | Context menu on symbol |
| `rip.impact` | RIP: Impact Analysis | Context menu on symbol |
| `rip.search` | RIP: Search Codebase | Command palette |
| `rip.showArchitecture` | RIP: Architecture | Command palette |
| `rip.showMetrics` | RIP: Metrics Dashboard | Command palette |
| `rip.indexRepo` | RIP: Index Repository | Command palette |
| `rip.checkStatus` | RIP: Check Status | Status bar click |

---

## Dependencies to Add

```json
{
  "dependencies": {
    "mermaid": "^10.9.0",              // Mermaid diagram rendering
    "marked": "^12.0.0",               // Markdown parsing
    "highlight.js": "^11.9.0"          // Code syntax highlighting
  },
  "devDependencies": {
    "@types/dompurify": "^3.0.0",      // XSS sanitization
    "dompurify": "^3.1.0"
  }
}
```

---

## Chat Panel UX Flow

### User opens chat (Ctrl+Shift+R):
```
┌──────────────────────────────────────────┐
│  🔍 RIP Chat                        [X]  │
├──────────────────────────────────────────┤
│                                          │
│  🤖 RIP is ready!                        │
│  📊 Indexed: 2,147 entities in 569 files │
│  🔗 Neo4j: Connected                     │
│  🧬 Qdrant: Ready                        │
│                                          │
│  Try asking:                             │
│  • "How does login work?"                │
│  • "Find authentication logic"           │
│  • "What depends on UserService?"        │
│  • "Show me the architecture"            │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ [auto ▼] Type your query...  [Send]│  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### User types "How does login work?":
```
┌──────────────────────────────────────────┐
│  🔍 RIP Chat                             │
├──────────────────────────────────────────┤
│  🧑 You: How does login work?            │
│                                          │
│  🤖 RIP: [auto-detected: explain flow]   │
│  ⏳ Tracing workflow...                   │
│                                          │
│  📋 Overview:                             │
│  The login flow authenticates users...    │
│                                          │
│  🌳 Workflow:                             │
│  LoginScreen → AuthProvider → AuthRepo   │
│  → AuthApi → POST /login                 │
│                                          │
│  📊 Mermaid Diagram: [Expand]             │
│  🔗 Dependencies: [View Table]            │
│                                          │
│  💡 Follow-up:                            │
│  • Trace AuthProvider                    │
│  • Check impact                          │
│  • Show files                            │
└──────────────────────────────────────────┘
```

---

## Implementation Plan

### Sprint 1: Foundation (3 days)
| Task | Description |
|------|-------------|
| Create `chatPanel.ts` | Main chat webview panel |
| Create `chatPanelProvider.ts` | Webview provider with message passing |
| Create `webviews/chat/` | HTML/CSS/JS for chat UI |
| Update `extension.ts` | Register chat panel, sidebar icon |
| Add `mermaid`, `marked`, `highlight.js` | Dependencies |

### Sprint 2: Intelligence (3 days)
| Task | Description |
|------|-------------|
| Create `intentRouter.ts` | Auto-detect command from natural language |
| Create `executionEngine.ts` | CLI-first execution with HTTP fallback |
| Create `cliExecutor.ts` | Spawn `uv run repo` subprocess |
| Update `apiClient.ts` | All endpoints, health check, correct paths |

### Sprint 3: Rich Responses (2 days)
| Task | Description |
|------|-------------|
| Create `responseComposer.ts` | Compose rich messages from command output |
| Create `sessionManager.ts` | Session context for follow-ups |
| Add Mermaid rendering | Render diagrams in chat |
| Add table rendering | Dependency/metrics tables |

### Sprint 4: Polish (2 days)
| Task | Description |
|------|-------------|
| Create `statusBar.ts` | Status bar with index count |
| Add context menu actions | Explain/Trace/Impact on right-click |
| Add keyboard shortcuts | Ctrl+Shift+R for chat, etc. |
| Error handling | Graceful degradation, retry logic |
| Streaming support | Stream LLM responses |

---

## Key Design Decisions

1. **CLI-first, not HTTP-first**: If `repo` command works in terminal, use it directly via subprocess. This eliminates server overhead and port conflicts. Only fall back to HTTP if the server is already running.

2. **Auto-detect, don't force selection**: The command dropdown defaults to "auto". RIP detects intent from the query. Users CAN override by selecting a specific command, but don't need to.

3. **Rich content in chat, not separate panels**: Everything renders inline in the chat — trees, diagrams, tables, code. No separate webview panels to manage. One unified experience.

4. **Session context for follow-ups**: The session manager tracks what was last explained/traced/searched so "what depends on it?" works naturally.

5. **No React/Vue dependency**: Plain HTML/CSS/JS with D3.js and Mermaid keeps the extension lightweight and avoids framework conflicts with VS Code.



Here's the concise prompt for the agent:

---

**PROMPT FOR AGENT:**

Rebuild the VS Code extension as a **single unified chat panel** (like Copilot/Cursor) backed by RIP's code intelligence. The user types natural language queries. RIP auto-detects intent, executes the right command (explain/search/trace/impact/architecture/metrics), and renders rich responses inline (Mermaid diagrams, trees, tables, code blocks). Session context persists across follow-ups ("what depends on it?").

## Architecture

**CLI-first execution**: If `repo` command works locally, spawn `uv run repo <command> <args> --json` as subprocess. No server overhead. Only fall back to HTTP API if CLI unavailable.

**Auto-detect, don't force**: Command dropdown defaults to "auto". Intent router detects from query patterns (how/explain → explain, find/search → search, trace/flow → trace, impact/depends → impact, architecture/structure → architecture). User CAN override by selecting specific command.

**Single chat panel**: Replace all individual panels (tracePanel, impactPanel, architecturePanel, dependencyGraphPanel) with one `chatPanel.ts`. Rich content types: text/markdown, tree view, mermaid diagram, table, code block, suggestions.

## Files to Create/Modify

| File | Purpose |
|------|---------|
| `src/panels/chatPanel.ts` | **NEW** — Main chat webview panel |
| `src/panels/chatPanelProvider.ts` | **NEW** — Webview provider with message passing |
| `src/intentRouter.ts` | **NEW** — Auto-detect command from query patterns |
| `src/executionEngine.ts` | **NEW** — CLI-first execution, HTTP fallback |
| `src/client/cliExecutor.ts` | **NEW** — Spawn `uv run repo` subprocess |
| `src/responseComposer.ts` | **NEW** — Compose structured content from CLI/API output |
| `src/sessionManager.ts` | **NEW** — Maintain context across messages |
| `src/statusBar.ts` | **NEW** — Status bar: indexed count, indexing progress |
| `src/extension.ts` | **UPDATE** — Register chat panel, sidebar icon, context menus |
| `src/client/apiClient.ts` | **UPDATE** — All endpoints, health check, correct paths/verbs |
| `webviews/chat/index.html` | **NEW** — Chat UI layout |
| `webviews/chat/chat.css` | **NEW** — Chat styling (bubbles, code blocks, diagrams) |
| `webviews/chat/chat.js` | **NEW** — Message rendering, Mermaid, D3, markdown |
| `package.json` | **UPDATE** — Add mermaid, marked, highlight.js; new commands |

## Dependencies to Add
```json
"mermaid": "^10.9.0",
"marked": "^12.0.0", 
"highlight.js": "^11.9.0"
```

## Commands to Register
- `rip.openChat` — Opens chat sidebar (Ctrl+Shift+R)
- `rip.explain` / `rip.trace` / `rip.impact` — Context menu on symbol
- `rip.search` / `rip.showArchitecture` / `rip.showMetrics` — Command palette
- `rip.checkStatus` — Status bar click

## Key Patterns

**Intent detection** (in `intentRouter.ts`):
- `how * work`, `explain`, `what is` → `explain`
- `find`, `search`, `where is`, `locate` → `search`
- `trace`, `call chain`, `flow`, `path` → `trace`
- `impact`, `depend`, `what breaks`, `affect` → `impact`

**CLI execution** (in `cliExecutor.ts`):
```typescript
const { stdout } = await execAsync(`uv run repo ${command} ${args} --json`, {
  cwd: workspaceRoot, timeout: 120000
});
return JSON.parse(stdout);
```

**Response composition** (in `responseComposer.ts`):
- Explain output → text overview + tree + mermaid + table + suggestions
- Search output → list with code previews
- Trace output → call chain visualization
- Impact output → affected files list with risk level

## Do NOT remove
- `hoverProvider.ts` — Keep hover explanations
- `codeActionProvider.ts` — Keep context menu actions
- `fileSaveWatcher.ts` — Keep auto-index on save

## Acceptance Criteria
1. Chat panel opens with Ctrl+Shift+R
2. Typing "How does login work?" auto-detects explain, shows tree + mermaid + LLM
3. Typing "Find authentication" auto-detects search, shows results
4. Follow-up "What depends on it?" uses session context
5. Status bar shows indexed count (green when ready)
6. Works without server running (uses CLI subprocess)
7. Falls back to HTTP if server is running

---