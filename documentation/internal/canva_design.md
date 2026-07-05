# Mobile Workflow Canvas: Complete Feature Specification

## Vision

A touch-first, n8n-style visual workflow builder that runs on a phone. Users drag blocks onto an infinite canvas, connect them with wires, tap any block to see its internal workings, and trigger the entire pipeline with a natural language query. This is not a simplified mobile version — it's the primary creation surface.

---

## Part 1: Canvas Interaction Model

### 1.1 Infinite Canvas

```
┌─────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────┐  │
│  │ 🔍 Search blocks    [Undo] [Redo] [✓]    │  │
│  │                                           │  │
│  │  ┌──────────┐                             │  │
│  │  │  🔍 RIP   │                             │  │
│  │  │  Search   │────┐                        │  │
│  │  └──────────┘    │                        │  │
│  │                   │    ┌──────────────┐    │  │
│  │                   ├───▶│  📊 RIP      │    │  │
│  │                   │    │  Trace Deps  │    │  │
│  │  ┌──────────┐     │    └──────┬───────┘    │  │
│  │  │  🐙 GitHub │     │           │           │  │
│  │  │  Commits   │──┐  │           │           │  │
│  │  └──────────┘  │  │           │           │  │
│  │                 │  │    ┌──────▼───────┐    │  │
│  │                 ├──┼───▶│  🤖 AI       │    │  │
│  │                 │  │    │  Analyze     │    │  │
│  │                 │  │    └──────┬───────┘    │  │
│  │                 │  │           │           │  │
│  │                 │  │    ┌──────▼───────┐    │  │
│  │                 │  │    │  ✅ Approval │    │  │
│  │                 │  │    │  Gate        │    │  │
│  │                 │  │    └──────┬───────┘    │  │
│  │                 │  │           │           │  │
│  │                 │  │    ┌──────▼───────┐    │  │
│  │                 │  │    │  📦 GitHub   │    │  │
│  │                 │  │    │  Create PR   │    │  │
│  │                 │  │    └──────────────┘    │  │
│  │                                           │  │
│  │                                    [▶ Run] │  │
│  └───────────────────────────────────────────┘  │
│                                                   │
│  [🟢 Trigger Query]  [🧩 Block Palette]  [⚙️]   │
└─────────────────────────────────────────────────┘
```

### 1.2 Canvas Gestures

| Gesture | Action |
|---|---|
| One finger drag on empty canvas | Pan the canvas |
| Pinch in/out | Zoom in/out (0.25x to 3x) |
| Double tap on empty canvas | Zoom to fit all blocks |
| One finger drag on block | Move block (wires follow) |
| Tap on block | Select block (shows properties panel) |
| Long press on block | Open block context menu |
| Tap on wire | Select wire (shows delete option) |
| One finger drag from block output port | Start new wire |
| Two finger tap | Quick action menu |
| Triple tap on canvas | Add block at that position |

### 1.3 Canvas Visual Language

```
BLOCK VISUAL DESIGN:

┌──────────────────────────────────────┐
│  🔍  RIP Semantic Search         ··· │  ← Header: icon + name + menu
│  ────────────────────────────────────│
│  Query: {{trigger_query}}            │  ← Preview of key bindings
│  Repo: payment-service               │
│  ────────────────────────────────────│
│  Status: ⏺ Ready                    │  ← Live status indicator
│  ●───────────────────────●           │  ← Input/output ports
│  IN                      OUT         │
└──────────────────────────────────────┘

PORT VISUALS:
  ● Input port (left side)  → glows blue when receiving connection
  ● Output port (right side) → glows green when has downstream
  ● Hovering port → enlarges, shows port name tooltip
  ● Dragging from port → wire preview follows finger

WIRE VISUALS:
  ───────────  Default wire (straight with rounded corners)
  ─ ─ ─ ─ ─ ─  Data flow animation (particles moving)
  ──────●●────  Selected wire (with handles)
  Red wire     = Error or broken connection
  Green wire   = Successfully executed
  Blue wire    = Currently executing
  Gray wire    = Not yet executed

BLOCK STATES:
  ⏺ White/neutral  = Ready, not executed
  🔵 Blue pulsing   = Currently executing
  ✅ Green check    = Completed successfully
  ❌ Red X          = Failed
  ⏸️ Yellow pause   = Awaiting approval/input
  ⬜ Gray outline   = Disabled/skipped
```

---

## Part 2: Block Palette (Bottom Sheet)

### 2.1 Palette Design

When user taps "Add Block" or "+" on canvas, a bottom sheet slides up:

```
┌─────────────────────────────────────────────────┐
│  [X]  Add Block                          [Search]│
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ All │ RIP │ GitHub │ AI │ Tools │ Flow │ Custom│  ← Category tabs
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  RIP Blocks                                       │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🔍  Semantic Search                         │ │
│  │     Find code by meaning, not keywords      │ │
│  │     Uses: 1,247 times this month            │ │
│  │                                  [Drag Me]  │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ 📊  Trace Dependencies                      │ │
│  │     Map all callers and callees             │ │
│  │     Uses: 892 times this month              │ │
│  │                                  [Drag Me]  │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🏗️  Architecture Overview                   │ │
│  │     Generate system architecture map         │ │
│  │     Uses: 456 times this month              │ │
│  │                                  [Drag Me]  │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ 💀  Dead Code Detection                      │ │
│  │     Find unused functions and classes        │ │
│  │     Uses: 234 times this month              │ │
│  │                                  [Drag Me]  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ⚡ AI Blocks                                     │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🤖  Analyze with AI                         │ │
│  │     Send context to LLM for reasoning        │ │
│  │     Default: Claude-4 | 3 more available    │ │
│  │                                  [Drag Me]  │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ 📝  Generate Code                           │ │
│  │     AI writes implementation code            │ │
│  │     Default: Claude-4 | 3 more available    │ │
│  │                                  [Drag Me]  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  🔧 Flow Control                                 │
│  ┌─────────────────────────────────────────────┐ │
│  │ ⏸️  Approval Gate                           │ │
│  │     Pause for human review                   │ │
│  │                                  [Drag Me]  │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🔀  Condition / Branch                       │ │
│  │     If/else logic based on prior output      │ │
│  │                                  [Drag Me]  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
└─────────────────────────────────────────────────┘
```

### 2.2 Drag-to-Canvas

User can either:
- Tap `[Drag Me]` → block appears at canvas center
- Long press block in palette → palette dismisses, block follows finger to desired position on canvas
- Swipe block left → block snaps to nearest available space on canvas

---

## Part 3: Block Detail View (Tap to Expand)

### 3.1 When User Taps a Block on Canvas

The block expands in-place to reveal its full configuration:

```
┌─────────────────────────────────────────────────┐
│  🔍  RIP Semantic Search                    [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  CONFIGURATION                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ Block Name                                  │ │
│  │ [Search payment codebase               ]    │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  INPUT BINDINGS                                  │
│  ┌─────────────────────────────────────────────┐ │
│  │ Query                                       │ │
│  │ ● From trigger query (user types at run)    │ │
│  │ ○ From previous block: [None selected  ▼]   │ │
│  │ ○ Fixed value: [                       ]    │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ Repository                                  │ │
│  │ ● Use current project (payment-service)     │ │
│  │ ○ Fixed value: [payment-service        ▼]   │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ Max Results                                 │ │
│  │ [10]  [ - ] [ + ]                           │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  BLOCK INFO                                      │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🔍  RIP Semantic Search                 v2.1│ │
│  │  Find code by meaning using hybrid search   │ │
│  │  (BM25 + embeddings + graph expansion)      │ │
│  │                                              │ │
│  │  Inputs:  query, repository, max_results     │ │
│  │  Outputs: files[], functions[], scores[]     │ │
│  │                                              │ │
│  │  ⚡ Capabilities: GRAPH_STORE, VECTOR_STORE  │ │
│  │  📊 Uses this month: 1,247                   │ │
│  │  ⏱️  Avg time: 1.2s                          │ │
│  │                                              │ │
│  │  [View Documentation] [See Examples]        │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [Save Changes]  [Duplicate Block]  [Delete]     │
└─────────────────────────────────────────────────┘
```

### 3.2 Block Detail for Different Block Types

**AI Block Detail:**
```
┌─────────────────────────────────────────────────┐
│  🤖  Analyze with AI                        [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  LLM SELECTION                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ ● Use workflow default (Claude-4)           │ │
│  │ ○ Override: [Claude-4 Opus           ▼]     │ │
│  │ ○ Let me pick at runtime                    │ │
│  │                                              │ │
│  │ Available models:                            │ │
│  │ ✅ Claude-4 (Default) | 128k ctx | $0.015/k  │ │
│  │ 🟡 GPT-5            | 64k ctx  | $0.010/k   │ │
│  │ 🟢 Ollama Local     | 32k ctx  | Free       │ │
│  │ ❌ Gemini (Disabled - no API key)            │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  PROMPT CONFIGURATION                            │
│  ┌─────────────────────────────────────────────┐ │
│  │ System Prompt Template                      │ │
│  │ [Root Cause Analysis v2.1            ▼]     │ │
│  │ [✏️ Edit Template]  [📋 View Rendered]      │ │
│  │ ─────────────────────────────────────────── │ │
│  │ Preview:                                     │ │
│  │ "You are analyzing a bug in {{repo}}.       │ │
│  │  Use ONLY the provided context. Cite file   │ │
│  │  paths and line numbers for every claim."   │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  TEMPERATURE & SETTINGS                          │
│  ┌─────────────────────────────────────────────┐ │
│  │ Temperature:  [0.3]  [━━━━●━━━━━]   Creative│ │
│  │ Max Tokens:    [4096]                        │ │
│  │ Stream Output: [✓] On                        │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  OUTPUT FORMAT                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ ● Auto-detect from prompt                   │ │
│  │ ○ Force JSON schema: [Upload Schema]        │ │
│  │ ○ Markdown / Free text                      │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [Save Changes]  [Test with Sample Input]        │
└─────────────────────────────────────────────────┘
```

**Approval Gate Detail:**
```
┌─────────────────────────────────────────────────┐
│  ⏸️  Approval Gate                          [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  WHEN TO PAUSE                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ ● Always pause (manual review required)     │ │
│  │ ○ Conditional:                              │ │
│  │   If risk score from previous block         │ │
│  │   [ >  ] [ 7  ]  (0-10 scale)              │ │
│  │   OR lines changed > [ 100  ]              │ │
│  │   OR files in: [ payment/, auth/      ]     │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  WHO CAN APPROVE                                 │
│  ┌─────────────────────────────────────────────┐ │
│  │ ● Me (workflow owner)                       │ │
│  │ ○ Anyone on this machine                    │ │
│  │ ○ Specific role: [None available - single   │ │
│  │                    user mode]               │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  APPROVAL INTERFACE                              │
│  ┌─────────────────────────────────────────────┐ │
│  │ Show approver:                              │ │
│  │ ☑ Full diff of changes                     │ │
│  │ ☑ Risk assessment from AI                  │ │
│  │ ☑ Files affected                           │ │
│  │ ☑ Test results (if available)              │ │
│  │ ☑ Dependency impact                        │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  TIMEOUT                                         │
│  ┌─────────────────────────────────────────────┐ │
│  │ If not approved within:                     │ │
│  │ [ 24 ] hours                                │ │
│  │ Then: ● Auto-reject  ○ Keep waiting        │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  APPROVAL METHOD                                 │
│  ┌─────────────────────────────────────────────┐ │
│  │ ☑ Mobile push notification                 │ │
│  │ ☑ In-app notification                      │ │
│  │ ☐ Email (not configured)                   │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**Deployment Block Detail:**
```
┌─────────────────────────────────────────────────┐
│  📦  GitHub: Create Pull Request            [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  PR CONFIGURATION                                │
│  ┌─────────────────────────────────────────────┐ │
│  │ Branch Name                                 │ │
│  │ ● Auto-generate from workflow name + date   │ │
│  │ ○ Custom prefix: [fix/                 ]    │ │
│  │ Preview: fix/bug-investigation-20240705     │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ PR Title                                    │ │
│  │ ● Auto-generate from AI summary             │ │
│  │ ○ Fixed: [                               ]  │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ PR Description                              │ │
│  │ ☑ Include AI analysis                      │ │
│  │ ☑ Include dependency graph                 │ │
│  │ ☑ Include test results                     │ │
│  │ ☑ Include workflow trace link              │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  REVIEWERS                                       │
│  ┌─────────────────────────────────────────────┐ │
│  │ ● None (self-review)                        │ │
│  │ ○ Auto-assign based on files:               │ │
│  │   payment/* → assign to code owners         │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  AUTO-MERGE                                      │
│  ┌─────────────────────────────────────────────┐ │
│  │ ☐ Auto-merge if tests pass                  │ │
│  │ ☐ Auto-merge after approval                 │ │
│  │ ● Manual merge (I'll merge myself)          │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  GITHUB CONNECTION                               │
│  │ ✅ Connected: payflow/payment-service         │ │
│  │ [Reconnect]  [Switch Repo]                   │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 3.3 Live Block Internals (During Execution)

When a workflow is running and user taps a block, they see live internals:

```
┌─────────────────────────────────────────────────┐
│  🤖  AI Analysis (RUNNING)                  [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  ⏱️  Elapsed: 3.2s                               │
│  📊 Tokens: 1,247 / 4,096                        │
│  💰 Cost so far: $0.018                          │
│                                                   │
│  INPUT CONTEXT (what the LLM received)           │
│  ┌─────────────────────────────────────────────┐ │
│  │ // 4,200 tokens assembled by Context Engine │ │
│  │                                              │ │
│  │ ## Bug Description                          │ │
│  │ International transfers over $10k failing   │ │
│  │                                              │ │
│  │ ## Relevant Code (from RIP Search)          │ │
│  │ src/services/CurrencyConverter.ts:45-78     │ │
│  │ [Show 34 lines]                             │ │
│  │                                              │ │
│  │ ## Dependency Graph (from RIP Trace)         │ │
│  │ CurrencyConverter.convertAndValidate()       │ │
│  │ ├── Called by: transferRoute.ts:45          │ │
│  │ ├── Called by: paymentHandler.ts:30         │ │
│  │ └── Calls: BankAdapter.validate()           │ │
│  │                                              │ │
│  │ ## Recent Commits (from GitHub)             │ │
│  │ 3 days ago: "Added $10k limit" - Mike       │ │
│  │ [Show diff]                                 │ │
│  │                                              │ │
│  │ [View Full Context] [Copy for Debug]        │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  LIVE OUTPUT (streaming)                         │
│  ┌─────────────────────────────────────────────┐ │
│  │ {                                           │ │
│  │   "root_cause": "The $10,000 limit check    │ │
│  │   in CurrencyConverter.ts:67 uses Math      │ │
│  │   .floor() instead of Math.round()...",     │ │
│  │   "confidence": "high",                     │ │
│  │   "affected_files": [▮                      │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [Cancel] [Pause] [Restart this block]           │
└─────────────────────────────────────────────────┘
```

---

## Part 4: Wire Connections & Data Flow

### 4.1 Drawing Wires

User drags from a block's output port (right side) to another block's input port (left side):

```
DRAG TO CONNECT:

   [Block A] ●━━━━━━━━━━━━━━━━━━━━━━━━━▶ ● [Block B]
              │                           │
              └─── Wire follows finger ───┘
              
   During drag:
   - Valid input ports glow blue (showing where you can connect)
   - Invalid ports stay gray (type mismatch or would create cycle)
   - Wire snaps to nearest valid port when released nearby
   - If released on empty canvas → context menu: "Connect to new block..."
```

### 4.2 Wire Properties (Tap on Wire)

```
┌─────────────────────────────────────────────────┐
│  Wire: RIP Search → AI Analysis             [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  DATA MAPPING                                    │
│  ┌─────────────────────────────────────────────┐ │
│  │ Source: RIP Search                          │ │
│  │ Output field: [top_result.files        ▼]   │ │
│  │                                              │ │
│  │ Target: AI Analysis                         │ │
│  │ Input field:  [context.code            ▼]   │ │
│  │                                              │ │
│  │ Mapping type:                               │ │
│  │ ● Direct pass-through                      │ │
│  │ ○ Transform: [No transform function    ]    │ │
│  │ ○ Pick specific fields                     │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ Data Preview (from last run)                │ │
│  │                                              │ │
│  │ Input: {                                    │ │
│  │   "files": ["CurrencyConverter.ts", ...],   │ │
│  │   "scores": [0.95, 0.87, ...]              │ │
│  │ }                                           │ │
│  │ Output: {                                   │ │
│  │   "code": ["CurrencyConverter.ts", ...]     │ │
│  │ }                                           │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  WIRE OPTIONS                                    │
│  ┌─────────────────────────────────────────────┐ │
│  │ ☑ Show data flow animation during run       │ │
│  │ ☑ Log data passing through this wire        │ │
│  │ Color: [Blue ▼]                             │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [Delete Wire]                                   │
└─────────────────────────────────────────────────┘
```

### 4.3 Multiple Inputs Merging

When two wires feed into the same block:

```
   [RIP Search] ────┐
                     ├───▶ [AI Analysis]
   [GitHub Commits] ─┘

   The AI Analysis block shows:
   ┌─────────────────────────────────────────────┐
   │ Input Mapping:                              │
   │  context.code    ← RIP Search.top_result    │
   │  context.commits ← GitHub Commits.commits   │
   │  context.trigger ← Trigger Query            │
   └─────────────────────────────────────────────┘
```

### 4.4 Branching (One Output → Multiple Inputs)

```
                      ┌──▶ [Approval Gate]
   [AI Analysis] ─────┤
                      └──▶ [Notification]

   Same output feeds both blocks in parallel.
   Visual: Wire splits with a small junction dot (●).
```

---

## Part 5: Canvas Toolbar & Controls

### 5.1 Top Toolbar

```
┌─────────────────────────────────────────────────┐
│  🔍 [Search blocks...]    [↩] [↪]  [100%] [✓]  │
│                                                   │
│  Search: Filters visible blocks by name           │
│  ↩ Undo: Last action (move, delete, connect)      │
│  ↪ Redo: Reversed undo                           │
│  100%: Zoom level (tap to reset 100%)            │
│  ✓: Save workflow                                │
└─────────────────────────────────────────────────┘
```

### 5.2 Bottom Toolbar

```
┌─────────────────────────────────────────────────┐
│  [🟢 Trigger]  [🧩 +Block]  [📋]  [⚙️]  [▶ Run] │
│                                                   │
│  🟢 Trigger: Configure how workflow starts        │
│  🧩 +Block: Open block palette                   │
│  📋: Canvas overview (minimap)                    │
│  ⚙️: Workflow settings                            │
│  ▶ Run: Execute the workflow                     │
└─────────────────────────────────────────────────┘
```

### 5.3 Minimap (Tap 📋)

```
┌─────────────────────────────────────────────────┐
│  Minimap (zoom out of full canvas)          [X] │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  · │ │
│  │  ·  ┌──┐      ┌──┐         ┌──┐     ·  ·  · │ │
│  │  ·  │  │──┐   │  │         │  │     ·  ·  · │ │
│  │  ·  └──┘  │   └──┘         └──┘     ·  ·  · │ │
│  │  ·        │    ·           ·  ·      ·  ·  · │ │
│  │  ·  ┌──┐  ├──────────────┐  ·      ·  ·  · │ │
│  │  ·  │  │──┘              │  ·      ·  ·  · │ │
│  │  ·  └──┘                 │  ·      ·  ·  · │ │
│  │  ·  ·  ·  ·  ·  ·  ·  · │  ·      ·  ·  · │ │
│  │  ·  ·  ·  ·  ·  ·  ·  · │  ·      ·  ·  · │ │
│  │  ·  ·  ·  ·  ·  ·  ·  ┌──┐·      ·  ·  · │ │
│  │  ·  ·  ·  ·  ·  ·  ·  │  │·      ·  ·  · │ │
│  │  ·  ·  ·  ·  ·  ·  ·  └──┘·      ·  ·  · │ │
│  └─────────────────────────────────────────────┘ │
│                     ┌──────┐                      │
│  Blue rectangle =   │ View │  (current viewport)  │
│                     └──────┘                      │
│                                                   │
│  Drag the blue rectangle to pan the main canvas   │
└─────────────────────────────────────────────────┘
```

---

## Part 6: Trigger Configuration

### 6.1 Trigger Block (Always on Canvas)

Every workflow has exactly one Trigger block. It's placed automatically, cannot be deleted, and defines how the workflow starts.

```
┌─────────────────────────────────────────────────┐
│  🟢  TRIGGER: Natural Language Query         [⚙️]│
│  ─────────────────────────────────────────────  │
│  "{{user types their question at runtime}}"     │
│                                                   │
│  ●───────────────────────●                       │
│  IN (none)               OUT → query, repo, user │
└─────────────────────────────────────────────────┘
```

### 6.2 Trigger Configuration (Tap ⚙️ on Trigger)

```
┌─────────────────────────────────────────────────┐
│  Trigger Configuration                       [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  TRIGGER TYPE                                    │
│  ┌─────────────────────────────────────────────┐ │
│  │ ● Natural Language Query (user types)       │ │
│  │   "transfers over $10k failing"             │ │
│  │                                              │ │
│  │ ○ Scheduled (cron)                          │ │
│  │   [0 2 * * 1       ] Every Monday 2 AM      │ │
│  │                                              │ │
│  │ ○ Webhook / API call                        │ │
│  │   Endpoint: /gateway/api/workflows/{id}/run │ │
│  │                                              │ │
│  │ ○ File watcher                              │ │
│  │   Watch: [src/services/          ]          │ │
│  │   On: [file changed ▼]                      │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  EXTRACTED PARAMETERS (from NL query)             │
│  ┌─────────────────────────────────────────────┐ │
│  │ Parameter      │ Bound to field             │ │
│  │ query           │ Trigger Query (full text)  │ │
│  │ bug_description │ Trigger Query (full text)  │ │
│  │ repository      │ Auto: current project      │ │
│  │ priority        │ Auto: medium               │ │
│  │                                              │ │
│  │ [+ Add extracted parameter]                 │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  REQUIRED INPUTS (block execution until provided) │
│  ┌─────────────────────────────────────────────┐ │
│  │ If query is missing required info:          │ │
│  │ ● Ask user to clarify (inline prompt)       │ │
│  │ ○ Use default: [                     ]      │ │
│  │ ○ Skip and continue with null               │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## Part 7: Workflow Settings

### 7.1 Settings Panel (Tap ⚙️ in bottom toolbar)

```
┌─────────────────────────────────────────────────┐
│  Workflow Settings                           [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ Name                                        │ │
│  │ [Bug Investigation - Payment Service   ]    │ │
│  └─────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ Description                                 │ │
│  │ [Traces bugs through code, commits, and     │ │
│  │  issues to find root cause              ]    │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  DEFAULT LLM                                     │
│  ┌─────────────────────────────────────────────┐ │
│  │ [Claude-4 (Default)                  ▼]     │ │
│  │ Individual blocks can override              │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  NOTIFICATIONS                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ On completion: ☑ Push  ☐ Email             │ │
│  │ On failure:    ☑ Push  ☑ Keep screen on    │ │
│  │ On approval:   ☑ Push  ☑ In-app badge      │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  MEMORY & LEARNING                               │
│  ┌─────────────────────────────────────────────┐ │
│  │ ☑ Save results to Personal Memory           │ │
│  │ ☑ Auto-tag with: bug, {{repo}}, {{date}}    │ │
│  │ ☑ Make available for future workflows       │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  EXECUTION                                       │
│  ┌─────────────────────────────────────────────┐ │
│  │ Timeout: [ 30 ] minutes                     │ │
│  │ On timeout: ● Stop  ○ Continue in bg        │ │
│  │ Max retries per block: [ 3 ]                │ │
│  │ Show live trace during run: ☑ On            │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [Save Settings]  [Export as Template]  [Share]  │
└─────────────────────────────────────────────────┘
```

---

## Part 8: Run Experience

### 8.1 Before Run (Trigger Input)

```
┌─────────────────────────────────────────────────┐
│  ▶ Run: Bug Investigation - Payment Service      │
│  ─────────────────────────────────────────────  │
│                                                   │
│  Describe what you need:                         │
│  ┌─────────────────────────────────────────────┐ │
│  │ International transfers over $10,000 are     │ │
│  │ failing with "Amount exceeds regulatory      │ │
│  │ limit" error. This started happening after   │ │
│  │ yesterday's deployment.                      │ │
│  │                                              │ │
│  │                                     [🎤 Mic] │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Repository: [payment-service         ▼]         │
│  Priority: [High ▼]                              │
│                                                   │
│  LLM to use: ● Workflow default (Claude-4)       │
│              ○ Override: [               ▼]      │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │              🚀 Start Workflow              │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Recent runs:                                    │
│  ✅ "Payment timeout bug" - 2h ago - 4m 12s     │
│  ✅ "Auth token refresh" - yesterday - 3m 47s   │
│  ❌ "Refund calculation" - yesterday - failed    │
└─────────────────────────────────────────────────┘
```

### 8.2 During Run (Live Canvas)

The canvas becomes live. Blocks animate as they execute:

```
┌─────────────────────────────────────────────────┐
│  🔵 Running: Bug Investigation     [12%] [⏸️] [■]│
│  ─────────────────────────────────────────────  │
│                                                   │
│  ┌──────────┐        ⏱️ 2.3s                      │
│  │ ✅ RIP    │                                     │
│  │ Search   │──┐                                  │
│  └──────────┘  │    ┌──────────────┐              │
│                 ├───▶│ ✅ RIP       │              │
│  ┌──────────┐  │    │ Trace Deps   │              │
│  │ ✅ GitHub │  │    └──────┬───────┘              │
│  │ Commits   │──┘           │                      │
│  └──────────┘               │    ⏱️ Running        │
│                              │                      │
│                       ┌──────▼───────┐              │
│                       │ 🔵 AI        │              │
│                       │ Analyze      │              │
│                       │ Tokens: 1.2k │              │
│                       └──────────────┘              │
│                              │                      │
│                       ┌──────▼───────┐              │
│                       │ ⬜ Approval  │  (waiting)   │
│                       │ Gate         │              │
│                       └──────┬───────┘              │
│                              │                      │
│                       ┌──────▼───────┐              │
│                       │ ⬜ GitHub    │  (waiting)   │
│                       │ Create PR    │              │
│                       └──────────────┘              │
│                                                   │
│  Live log:                                        │
│  ┌─────────────────────────────────────────────┐ │
│  │ [09:23:01] RIP Search: Found 12 relevant    │ │
│  │ [09:23:02] RIP Trace: 7 callers, 3 callees │ │
│  │ [09:23:03] GitHub: 5 recent commits found   │ │
│  │ [09:23:04] AI: Analyzing... ████░░░░ 48%   │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [View Full Trace]  [Cancel Run]                  │
└─────────────────────────────────────────────────┘
```

### 8.3 Approval During Run

When an Approval Gate block activates:

```
┌─────────────────────────────────────────────────┐
│  ⏸️  Approval Required                           │
│  ─────────────────────────────────────────────  │
│                                                   │
│  Workflow: Bug Investigation - Payment Service    │
│  Block: AI Analysis complete → needs review      │
│                                                   │
│  AI FOUND:                                       │
│  ┌─────────────────────────────────────────────┐ │
│  │ Root cause: Math.floor() instead of         │ │
│  │ Math.round() in CurrencyConverter.ts:67     │ │
│  │                                              │ │
│  │ Confidence: HIGH (94%)                       │ │
│  │                                              │ │
│  │ Proposed fix: Change Math.floor to           │ │
│  │ Math.round on line 67. 1-line change.        │ │
│  │                                              │ │
│  │ Risk: LOW - No API changes, no dependency    │ │
│  │ changes, all existing tests should pass      │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  EVIDENCE:                                        │
│  ┌─────────────────────────────────────────────┐ │
│  │ 📄 CurrencyConverter.ts:67                  │ │
│  │ [View affected file with diff]              │ │
│  │                                              │ │
│  │ 📊 Dependency Impact:                       │ │
│  │ [View full dependency graph]                │ │
│  │                                              │ │
│  │ 📝 Recent Commits:                          │ │
│  │ [View commits that touched this file]       │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ ✅ Approve & Continue                       │ │
│  │ ❌ Reject & Stop                            │ │
│  │ 💬 Request Changes...                       │ │
│  │ ⏭️ Skip this block (approve nothing)        │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## Part 9: Block Library Management

### 9.1 Custom Block Registration

Users can register custom blocks from MCP servers or create composite blocks:

```
┌─────────────────────────────────────────────────┐
│  My Blocks                                   [+] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  Built-in (18)                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ RIP Search, RIP Trace, RIP Architecture...  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  From Integrations (5)                           │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🐙 GitHub: Commits, PRs, Issues, Actions    │ │
│  │ 📋 Jira: Issues, Boards                     │ │
│  │ 💬 Slack: Messages, Search                  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Custom MCP (2)                                  │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🧪 Internal Test Runner                     │ │
│  │ 🔒 Security Scanner (v2.1)                  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  My Composite Blocks (1)                         │
│  ┌─────────────────────────────────────────────┐ │
│  │ 📦 "Full Bug Fix Pipeline"                  │ │
│  │     RIP Search → Trace → AI → Test → PR     │ │
│  │     [Edit] [Use] [Delete]                   │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [+ Register New Block from MCP Server]          │
│  [+ Create Composite Block from Selection]       │
└─────────────────────────────────────────────────┘
```

### 9.2 Create Composite Block

User selects multiple blocks on canvas → "Group into Composite Block":

```
1. Select blocks on canvas (multi-tap or lasso)
2. Context menu → "Group into Composite Block"
3. Name it: "Full Bug Fix Pipeline"
4. Define which inputs/outputs are exposed externally
5. Save → appears in My Blocks palette
6. Can now be dropped as a single block in any workflow
```

---

## Part 10: Template System

### 10.1 Save as Template

```
┌─────────────────────────────────────────────────┐
│  Save as Template                            [X] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  Template Name:                                  │
│  [Bug Investigation with Auto-Fix           ]    │
│                                                   │
│  Category:                                       │
│  [Investigation ▼]                               │
│                                                   │
│  Description:                                    │
│  [Traces bugs through code, commits, and        │ │
│   issues, finds root cause, generates fix,      │ │
│   runs tests, and opens a PR automatically.     │ │
│   Best for: reproducible bugs in known modules.] │ │
│                                                   │
│  Tags: [bug] [investigation] [auto-fix] [+Add]   │
│                                                   │
│  Template Preview:                               │
│  ┌─────────────────────────────────────────────┐ │
│  │ [Mini canvas preview with blocks]           │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Visibility:                                     │
│  ● Private (only me)                            │
│  ○ Shared on this machine                       │
│                                                   │
│  Included with template:                         │
│  ☑ Workflow blocks and connections               │
│  ☑ Block configurations                          │
│  ☑ Prompt templates                              │
│  ☑ Default LLM settings                         │
│  ☐ Sample trigger queries                       │
│  ☐ Example output                               │
│                                                   │
│  [Save Template]  [Save & Share]                │
└─────────────────────────────────────────────────┘
```

### 10.2 Template Gallery

```
┌─────────────────────────────────────────────────┐
│  Template Gallery                           [🔍] │
│  ─────────────────────────────────────────────  │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ All │ Investigation │ Fix │ Audit │ Custom  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ ⭐ Bug Investigation with Auto-Fix          │ │
│  │    My template • Used 23 times              │ │
│  │    ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐           │ │
│  │    │🔍│─▶│📊│─▶│🤖│─▶│🧪│─▶│📦│           │ │
│  │    └──┘  └──┘  └──┘  └──┘  └──┘           │ │
│  │                                 [Use] [Edit] │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🔒 Security Audit (Built-in)                │ │
│  │    Vulnerability scan + dependency check     │ │
│  │    ┌──┐  ┌──┐  ┌──┐  ┌──┐                  │ │
│  │    │🔍│─▶│🔒│─▶│🤖│─▶│📋│                  │ │
│  │    └──┘  └──┘  └──┘  └──┘                  │ │
│  │                                 [Use] [View] │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🏗️ Architecture Overview (Built-in)         │ │
│  │    Generate system architecture from code     │ │
│  │    ┌──┐  ┌──┐  ┌──┐                         │ │
│  │    │🏗️│─▶│📊│─▶│🤖│                         │ │
│  │    └──┘  └──┘  └──┘                         │ │
│  │                                 [Use] [View] │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [+ Create New Template]                         │
└─────────────────────────────────────────────────┘
```

---

## Part 11: Technical Implementation Notes

### 11.1 Data Model for Canvas

```yaml
WorkflowCanvas:
  id: uuid
  workflow_id: uuid
  blocks:
    - id: uuid
      block_type_id: "rip.search"
      position: {x: 150, y: 200}        # Canvas coordinates
      config: {limit: 10, ...}          # Block-specific config
      input_bindings:
        query: {source: "trigger_query"}
        repository: {source: "fixed", value: "payment-service"}
  wires:
    - id: uuid
      source_block_id: uuid
      source_port: "output"
      target_block_id: uuid
      target_port: "query"
      mapping:
        type: "direct" | "transform" | "pick_fields"
        transform_function: null | string
        field_map: null | {source_field: target_field}
  viewport:
    zoom: 1.0
    center: {x: 500, y: 300}
  created_at: timestamp
  updated_at: timestamp
```

### 11.2 Rendering Engine

Use Flutter's `CustomPainter` for the canvas:

```dart
class WorkflowCanvas extends StatefulWidget {
  // Infinite canvas with:
  // - CustomPainter for wires (bezier curves with animated dashes)
  // - Stack of Positioned widgets for blocks
  // - GestureDetector for pan/zoom/drag
  // - InteractiveViewer for built-in pan/zoom support
}

class WirePainter extends CustomPainter {
  // Draws animated bezier curves between ports
  // Particle animation shows data flow direction
  // Color changes based on wire state (running/completed/error)
}
```

### 11.3 Port Connection Logic

```dart
class PortConnector {
  // When user drags from output port:
  // 1. Show wire preview following finger
  // 2. Highlight valid input ports (type-compatible, no cycles)
  // 3. On release near valid port → snap connection
  // 4. On release elsewhere → show context menu
  
  bool isValidConnection(BlockPort source, BlockPort target) {
    // Check: target is input port
    // Check: source.output_type compatible with target.input_type
    // Check: no circular dependency (DFS from target back to source)
    // Check: target doesn't already have a connection (unless multi-input)
  }
}
```

### 11.4 Offline Support

Canvas state saved locally via Drift (already used in Flutter app):

```dart
// Auto-save every 5 seconds + on every meaningful action
// Sync with server when online
// Conflict resolution: server version wins, local changes merged
```

---

## Part 12: Summary of Mobile Canvas Features

| Feature | Description |
|---|---|
| Infinite canvas | Pan, zoom, place blocks anywhere |
| Drag-drop blocks | From palette to canvas, or palette dismisses and block follows finger |
| Wire connections | Drag from output port to input port, bezier curves, animated data flow |
| Block detail | Tap any block to expand and see full configuration, internals, live state |
| Live execution view | Blocks animate during run, show tokens/cost/progress, streaming output |
| Trigger block | Always present, defines how workflow starts (NL query, schedule, webhook) |
| Approval gates | Pause execution, show evidence, approve/reject from phone |
| Composite blocks | Group multiple blocks into reusable single block |
| Templates | Save canvas as template, browse gallery, clone and modify |
| Minimap | Overview of full canvas, drag to navigate |
| Undo/redo | Full action history |
| Offline | Canvas state saved locally, syncs when connected |
| Block palette | Categorized, searchable, shows usage stats |
| Wire data mapping | Tap wire to configure field-level mapping between blocks |
| Custom blocks | Register from MCP servers or create composites |