# RIP Flutter App — Complete Redesign & Implementation Plan

> **Goal**: A production-grade, Claude/ChatGPT-quality mobile AI chat app that connects to the RIP backend with proper API wiring, rich response rendering, and a dark, minimal, modern design.

---

## Why the Current Build Failed

| Problem | Root Cause |
|---------|-----------|
| Ugly UI with random padding/colors | No design system. Used raw Material defaults |
| `/commands` not wired to APIs | `_sendMessage()` only returns a hardcoded string — never calls `RipClient` |
| Only one response type | No response parsing. All API responses dumped as plain text |
| No real connection flow | `connectionStatusProvider` exists but chat ignores it |
| Overlays not functional | `CommandPalette` and `ProjectSwitcher` exist but don't trigger API calls |
| Drawer is static | `AppDrawer` renders but doesn't load real projects or route actions |

---

## Design System (Reference: Provided Screenshot)

### Color Palette
```dart
// Dark theme (primary)
background:     #0D0D0D   // near-black canvas
surface:        #1A1A1A   // card/bubble background
surfaceVariant: #242424   // input bar, overlays
border:         #2A2A2A   // subtle separators
primary:        #7C3AED   // RIP purple (avatar, send button, chips)
onPrimary:      #FFFFFF
success:        #22C55E   // connected dot
warning:        #F59E0B   // Impact Analysis badge
error:          #EF4444   // High risk badge

// Text
textPrimary:    #F5F5F5
textSecondary:  #9CA3AF
textMuted:      #6B7280
```

### Typography
```dart
// Use Inter via google_fonts
headingLg:  Inter 20sp / W600
headingMd:  Inter 16sp / W600
bodyMd:     Inter 14sp / W400
bodySm:     Inter 13sp / W400
caption:    Inter 12sp / W400
mono:       JetBrainsMono 13sp (code blocks)
```

### Component Tokens
```
borderRadius.card:    12px
borderRadius.bubble:  16px (user) / 4px tl (RIP)
borderRadius.chip:    100px (pill)
borderRadius.input:   28px
spacing.xs:   4px
spacing.sm:   8px
spacing.md:   16px
spacing.lg:   24px
iconSize.sm:  18px
iconSize.md:  22px
```

---

## App Architecture (Clean, No Junk)

```
lib/
├── main.dart
├── app.dart                          # ProviderScope + MaterialApp.router
│
├── core/
│   ├── design/
│   │   ├── app_colors.dart           # All color constants
│   │   ├── app_text_styles.dart      # All text styles
│   │   ├── app_theme.dart            # ThemeData (dark + light)
│   │   └── app_spacing.dart          # Padding/margin constants
│   ├── api/
│   │   ├── rip_client.dart           # Dio HTTP client (ALL endpoints)
│   │   └── rip_ws_client.dart        # WebSocket for indexing
│   ├── constants.dart
│   └── exceptions.dart
│
├── data/
│   ├── models/
│   │   ├── project.dart
│   │   ├── message.dart              # Includes RipResponseBlock list
│   │   ├── rip_response.dart         # Parsed response: blocks of typed content
│   │   ├── index_job.dart
│   │   ├── search_result.dart
│   │   └── server_config.dart
│   └── local/
│       └── app_database.dart         # Drift: messages table
│
├── presentation/
│   ├── providers/
│   │   ├── settings_provider.dart
│   │   ├── connection_provider.dart
│   │   ├── project_provider.dart
│   │   ├── chat_provider.dart        # THE brain — command routing + API calls
│   │   └── index_provider.dart
│   │
│   ├── screens/
│   │   ├── splash_screen.dart
│   │   ├── setup_screen.dart
│   │   └── chat_screen.dart          # ONLY main screen
│   │
│   └── widgets/
│       ├── chat/
│       │   ├── message_list.dart
│       │   ├── user_bubble.dart
│       │   ├── rip_bubble.dart       # Renders RipResponseBlock list
│       │   └── typing_indicator.dart
│       ├── response_blocks/          # ONE widget per block type
│       │   ├── text_block.dart       # Markdown
│       │   ├── workflow_tree_block.dart
│       │   ├── mermaid_block.dart
│       │   ├── table_block.dart
│       │   ├── code_block.dart
│       │   ├── file_list_block.dart
│       │   ├── impact_block.dart
│       │   └── suggestion_chips_block.dart
│       ├── overlays/
│       │   ├── command_palette.dart
│       │   ├── project_switcher.dart
│       │   └── add_repo_sheet.dart
│       ├── sidebar/
│       │   └── app_drawer.dart
│       └── common/
│           ├── status_dot.dart
│           ├── section_card.dart     # The dark bordered card used for all blocks
│           ├── count_badge.dart
│           └── error_banner.dart
│
└── utils/
    ├── response_parser.dart          # Parses raw API text → List<RipResponseBlock>
    ├── command_parser.dart
    └── date_formatter.dart
```

---

## The Core Problem to Fix First: Chat Provider

The current `_sendMessage()` does this:
```dart
// WRONG — never calls RIP API
await Future.delayed(const Duration(seconds: 1));
await ref.read(chatProvider.notifier).addRipMessage('sample response');
```

It must do this:

```dart
Future<void> _sendMessage(String text) async {
  if (text.isEmpty) return;

  // 1. Parse command vs natural language
  final parsed = CommandParser.parse(text);

  // 2. Add user message
  final userMsg = Message.user(text);
  state = [...state, userMsg];

  // 3. Add pending RIP message (typing state)
  final pendingId = uuid.v4();
  state = [...state, Message.pending(pendingId)];

  try {
    // 4. Route to correct API endpoint
    final response = await _executeCommand(parsed);

    // 5. Parse API response into typed blocks
    final blocks = ResponseParser.parse(response, commandType: parsed.type);

    // 6. Replace pending with real response
    state = state.map((m) =>
      m.id == pendingId ? Message.rip(blocks) : m
    ).toList();

  } catch (e) {
    state = state.map((m) =>
      m.id == pendingId ? Message.error(e.toString()) : m
    ).toList();
  }
}

Future<String> _executeCommand(ParsedCommand cmd) {
  final client = ref.read(ripClientProvider);
  final projectId = ref.read(activeProjectProvider)?.projectId;

  return switch (cmd.type) {
    CommandType.search       => client.search(query: cmd.args['query']!, projectId: projectId),
    CommandType.explain      => client.explain(query: cmd.args['query']!, projectId: projectId),
    CommandType.trace        => client.trace(symbol: cmd.args['symbol']!, projectId: projectId),
    CommandType.impact       => client.impact(symbol: cmd.args['symbol']!, projectId: projectId),
    CommandType.architecture => client.architecture(projectId: projectId),
    CommandType.metrics      => client.metrics(projectId: projectId),
    CommandType.onboard      => client.onboard(projectId: projectId),
    CommandType.deadCode     => client.deadCode(projectId: projectId),
    CommandType.naturalLang  => client.explain(query: cmd.raw, projectId: projectId),
    _ => throw UnimplementedError(cmd.type.name),
  };
}
```

---

## Response Model (Critical Missing Piece)

```dart
// data/models/rip_response.dart

enum BlockType {
  text,
  workflowTree,
  mermaid,
  table,
  code,
  fileList,
  impact,
  suggestionChips,
}

class RipResponseBlock {
  final BlockType type;
  final dynamic data;   // String for text/mermaid/code, List for tree/table/files/chips
  final String? title;
  final String? subtitle;
  final int? count;
  final String? severity; // "High", "Medium", "Low" for impact
}

class RipResponse {
  final List<RipResponseBlock> blocks;
}
```

---

## Response Parser

The API returns raw text/markdown. We need to parse it into blocks:

```dart
// utils/response_parser.dart

class ResponseParser {
  static List<RipResponseBlock> parse(String raw, {required CommandType commandType}) {
    final blocks = <RipResponseBlock>[];

    // 1. Extract Mermaid diagrams
    final mermaidRegex = RegExp(r'```mermaid\n([\s\S]*?)```');
    // 2. Extract code blocks
    final codeRegex = RegExp(r'```(\w+)?\n([\s\S]*?)```');
    // 3. Parse tree sections (indented lines after "Workflow:" or "Trace:")
    // 4. Parse table sections (markdown tables |---|)
    // 5. Parse file paths (lines starting with src/, lib/, etc.)
    // 6. Generate suggestion chips based on commandType
    // 7. Remaining text = markdown text block

    // Always append suggestion chips
    blocks.add(RipResponseBlock(
      type: BlockType.suggestionChips,
      data: _suggestionsFor(commandType),
    ));

    return blocks;
  }

  static List<String> _suggestionsFor(CommandType type) => switch (type) {
    CommandType.explain => ['Show state flow', 'Show impact', 'Show consumers', 'Find similar'],
    CommandType.trace   => ['Show full chain', 'Show impact', 'What calls this?'],
    CommandType.search  => ['Explain this', 'Trace this', 'Show impact'],
    _                   => ['Search', 'Explain', 'Architecture'],
  };
}
```

---

## Screen-by-Screen Rebuild

### 1. Chat Screen (Pixel-Perfect to Screenshot)

```
AppBar:
  - Left: Hamburger (≡)
  - Center: RIP logo + "Workspace Connected" pill with green dot + chevron
  - Right: Filter/settings icon

Body:
  - ListView of messages (reverse: false, scroll to bottom on new msg)
  - User bubbles: right-aligned, dark surface card, avatar "D", timestamp
  - RIP bubbles: left-aligned, no background, RIP logo avatar, "AI" chip, timestamp

  RIP Response anatomy:
  ┌──────────────────────────────────────┐
  │ "Here's how login works..."          │ ← text block (Markdown)
  │                                      │
  │ ┌──────────────────────────────────┐ │
  │ │ [icon] Workflow Tree   8 nodes ⌄ │ │ ← SectionCard (expandable)
  │ │ LoginScreen → AuthProvider → ... │ │
  │ └──────────────────────────────────┘ │
  │ ┌──────────────────────────────────┐ │
  │ │ [icon] Mermaid Diagram  Preview ⌄│ │
  │ └──────────────────────────────────┘ │
  │ ┌──────────────────────────────────┐ │
  │ │ [icon] Dependencies       12  ⌄ │ │
  │ └──────────────────────────────────┘ │
  │ ┌──────────────────────────────────┐ │
  │ │ [icon] State Flow      5 steps ⌄ │ │
  │ └──────────────────────────────────┘ │
  │ ┌──────────────────────────────────┐ │
  │ │ [icon] Important Files       6 ⌄ │ │
  │ └──────────────────────────────────┘ │
  │ ┌──────────────────────────────────┐ │
  │ │ [icon] Impact Analysis   [High] ⌄│ │
  │ └──────────────────────────────────┘ │
  │                                      │
  │ Follow up                            │
  │ [Show state flow][Show impact][...]  │ ← pill chips, horizontally scrollable
  └──────────────────────────────────────┘

InputBar (bottom):
  - [+] button (attach/add repo)
  - [Auto ⌄] model picker pill  
  - TextField: "Ask anything about your codebase..."
  - [↑] send button (purple circle)
```

### 2. SectionCard Widget (Core Reusable)

```dart
class SectionCard extends StatefulWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final String? trailingLabel;  // "8 nodes", "Preview", "High"
  final Color? trailingColor;   // null = grey, red = high, etc.
  final Widget? expandedChild;
  final bool initiallyExpanded;
}
```

Every block (Workflow Tree, Mermaid, Dependencies, State Flow, Important Files, Impact) is a `SectionCard`. They all look the same — dark background `#1A1A1A`, rounded 12px, border `#2A2A2A`, chevron right.

### 3. Setup Screen

```
Dark fullscreen:
  RIP logo + name (centered, top third)
  
  "Connect to your RIP server"
  
  TextField: Server URL
    placeholder: "http://192.168.1.100:8000"
    
  TextField: API Key (optional)
    placeholder: "rip_xxxxxxxxxxxx"
    trailing: eye icon
  
  [Test Connection]  → shows green ✓ or red ✗ inline
  
  [Connect →]  → purple filled button, full width
  
  Footer: "Need help? Run 'repo serve' on your server"
```

### 4. Sidebar Drawer

```
Dark panel, slides from left:

  Header:
    RIP logo
    Server URL (truncated)
    Status dot + "Connected" / "Disconnected"

  ─── Projects ───
  [Each project row]:
    folder icon | Project Name | ✅ indexed
    Tapping sets activeProject

  [+ Add Repository]  → opens AddRepoSheet

  ─── Recent Chats ───
  Today
    • "How does login work?"
    • "Trace AuthProvider"
  Yesterday
    • "Architecture overview"

  ─── Settings ───
  Theme toggle (Dark / Light / System)
  Server config → goes to setup screen
  Clear history

  ─── About ───
  Version, GitHub link
```

---

## Command Palette (Properly Wired)

Appears as a bottom sheet when user types `/`:

```
╔══════════════════════════════╗
║  Commands                 ✕  ║
║  ┌─────────────────────────┐ ║
║  │ 🔍 /search <query>      │ ║  → GET /search?q=&project_id=
║  │ Semantic codebase search │ ║
║  ├─────────────────────────┤ ║
║  │ 💡 /explain <topic>     │ ║  → POST /explain
║  │ Architecture explanation │ ║
║  ├─────────────────────────┤ ║
║  │ 🌲 /trace <symbol>      │ ║  → GET /trace/{symbol}
║  │ Call chain tracing       │ ║
║  ├─────────────────────────┤ ║
║  │ 💥 /impact <symbol>     │ ║  → GET /impact/{symbol}
║  ├─────────────────────────┤ ║
║  │ 🏗️  /architecture        │ ║  → GET /architecture
║  ├─────────────────────────┤ ║
║  │ 📊 /metrics              │ ║  → GET /metrics
║  ├─────────────────────────┤ ║
║  │ 🚀 /onboard              │ ║  → GET /onboard
║  ├─────────────────────────┤ ║
║  │ 🔗 /dependencies <file> │ ║  → GET /dependencies
║  ├─────────────────────────┤ ║
║  │ ➕ /index <git-url>     │ ║  → POST /git/index + WS
║  ├─────────────────────────┤ ║
║  │ ☠️  /dead-code           │ ║  → GET /dead-code
║  └─────────────────────────┘ ║
╚══════════════════════════════╝
```

When user selects a command that needs arguments, the input bar pre-fills `/explain ` and they type the rest.

---

## API Client (Complete — All Endpoints)

```dart
class RipClient {
  final Dio _dio;

  // Health
  Future<bool> healthCheck() → GET /health

  // Projects
  Future<List<Project>> listProjects() → GET /projects/
  Future<Project> getProject(String id) → GET /projects/{id}
  Future<void> deleteProject(String id) → DELETE /projects/{id}

  // Git Indexing
  Future<IndexJob> startIndexing({
    required String gitUrl,
    String? projectName,
    String? branch,
  }) → POST /git/index

  Future<IndexJob> getJobStatus(String jobId) → GET /git/status/{jobId}
  Future<List<IndexJob>> listJobs() → GET /git/jobs

  // Intelligence (all accept optional projectId)
  Future<String> search({
    required String query,
    int limit = 10,
    String? projectId,
  }) → GET /search

  Future<String> explain({
    required String query,
    String? projectId,
    bool diagram = true,
    bool tree = true,
    bool deps = true,
  }) → POST /explain

  Future<String> trace({
    required String symbol,
    String? projectId,
    int depth = 3,
  }) → GET /trace/{symbol}

  Future<String> impact({
    required String symbol,
    String? projectId,
  }) → GET /impact/{symbol}

  Future<String> architecture({String? projectId}) → GET /architecture

  Future<String> metrics({
    String? module,
    String? projectId,
  }) → GET /metrics

  Future<String> onboard({String? projectId}) → GET /onboard

  Future<String> deadCode({String? projectId}) → GET /dead-code

  Future<String> dependencies({
    required String file,
    String? projectId,
  }) → GET /dependencies
}
```

Auth header: `Authorization: Bearer $apiKey` (added via Dio interceptor if key is set).

---

## WebSocket Flow (Add Repository)

```dart
// In AddRepoSheet:
1. User enters git URL + project name
2. Tap [Index Repository]
3. Call POST /git/index → get jobId
4. Connect WS: ws://$serverUrl/ws/index/$jobId
5. Stream messages into chat inline:
   "📦 Cloning repository..."
   "🔍 Parsing 847 files..."
   "🧠 Building knowledge graph..."
   "🔮 Generating embeddings..."
   "✅ Indexed 2,147 entities across 569 files!"
6. On complete: refresh project list, set active project
7. Close sheet
```

---

## Implementation Order (Do This Exactly)

### Phase 0 — Design Foundation (Day 1)
1. `core/design/app_colors.dart` — all color constants
2. `core/design/app_text_styles.dart` — Inter + JetBrains Mono
3. `core/design/app_theme.dart` — dark ThemeData wired to above
4. `core/design/app_spacing.dart` — spacing/radius tokens
5. Verify `flutter pub get` and `flutter analyze` on design files only

### Phase 1 — API Layer (Day 1-2)
6. `core/api/rip_client.dart` — complete Dio client, all endpoints
7. `core/api/rip_ws_client.dart` — WebSocket for indexing
8. `data/models/*.dart` — all models
9. `utils/response_parser.dart` — parses raw API text → blocks
10. `utils/command_parser.dart` — parses `/search foo` → ParsedCommand

### Phase 2 — Providers + State (Day 2)
11. `settings_provider.dart` — server URL, API key, theme (SharedPreferences)
12. `connection_provider.dart` — health check, auto-retry
13. `project_provider.dart` — list, active, refresh
14. `chat_provider.dart` — THE core: command routing, API calls, state
15. `index_provider.dart` — job tracking, WS connection

### Phase 3 — Common Widgets (Day 2-3)
16. `widgets/common/section_card.dart` — the expandable dark card
17. `widgets/common/status_dot.dart`
18. `widgets/common/count_badge.dart`
19. `widgets/common/error_banner.dart`

### Phase 4 — Response Block Widgets (Day 3)
20. `response_blocks/text_block.dart` — flutter_markdown
21. `response_blocks/workflow_tree_block.dart` — indented, expandable nodes
22. `response_blocks/mermaid_block.dart` — WebView or flutter_svg fallback
23. `response_blocks/table_block.dart` — horizontal scroll DataTable
24. `response_blocks/code_block.dart` — flutter_highlight + copy
25. `response_blocks/file_list_block.dart` — tappable rows
26. `response_blocks/impact_block.dart` — with severity badge
27. `response_blocks/suggestion_chips_block.dart` — horizontal pill chips

### Phase 5 — Chat Widgets (Day 3-4)
28. `widgets/chat/user_bubble.dart` — right-aligned, avatar
29. `widgets/chat/rip_bubble.dart` — renders List<RipResponseBlock>
30. `widgets/chat/typing_indicator.dart` — 3 dots animation
31. `widgets/chat/message_list.dart` — ListView.builder

### Phase 6 — Overlays (Day 4)
32. `widgets/overlays/command_palette.dart` — bottom sheet, filterable
33. `widgets/overlays/project_switcher.dart` — bottom sheet, project list
34. `widgets/overlays/add_repo_sheet.dart` — form + WS progress

### Phase 7 — Screens (Day 4-5)
35. `presentation/screens/splash_screen.dart`
36. `presentation/screens/setup_screen.dart` — URL + API key + test
37. `presentation/screens/chat_screen.dart` — final assembly

### Phase 8 — Sidebar (Day 5)
38. `widgets/sidebar/app_drawer.dart` — full sidebar as per spec

### Phase 9 — Validation (Day 5-6)
39. `flutter analyze` → 0 errors
40. `flutter build apk --debug` → builds
41. Manual test: setup → connect → chat → `/search` → response renders
42. Manual test: `/explain "login"` → all 6 section cards render
43. Manual test: `/index <url>` → WS progress in AddRepoSheet
44. Manual test: `@` project switcher → switches context
45. Manual test: drawer → projects load → settings work

---

## pubspec.yaml (Final)

```yaml
name: rip_app
description: RIP - Repository Intelligence Platform Mobile Client
version: 1.0.0+1

environment:
  sdk: '>=3.3.0 <4.0.0'
  flutter: '>=3.22.0'

dependencies:
  flutter:
    sdk: flutter

  # State
  flutter_riverpod: ^2.5.1
  riverpod_annotation: ^2.3.5

  # HTTP + WS
  dio: ^5.6.0
  web_socket_channel: ^3.0.1

  # Navigation
  go_router: ^14.2.7

  # Storage
  shared_preferences: ^2.3.2
  drift: ^2.20.3
  sqlite3_flutter_libs: ^0.5.24

  # UI
  flutter_markdown: ^0.7.3
  flutter_highlight: ^0.7.0
  google_fonts: ^6.2.1
  webview_flutter: ^4.8.0  # for Mermaid

  # Models
  freezed_annotation: ^2.4.4
  json_annotation: ^4.9.0
  equatable: ^2.0.5
  uuid: ^4.4.2
  intl: ^0.19.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  build_runner: ^2.4.12
  freezed: ^2.5.7
  json_serializable: ^6.8.0
  riverpod_generator: ^2.4.3
  drift_dev: ^2.20.3
  flutter_lints: ^4.0.0
```

---

## Critical Anti-Patterns to Avoid

| ❌ Don't | ✅ Do |
|----------|-------|
| `Future.delayed` fake responses | Real `RipClient` API calls |
| `withOpacity(0.3)` (deprecated) | `withValues(alpha: 0.3)` |
| `Colors.black54` overlays | `AppColors.surface.withValues(alpha: 0.8)` |
| Hardcoded `Colors.purple` | `Theme.of(context).colorScheme.primary` |
| `print()` debug logs | Proper logger or remove |
| Nested `Column` inside `SingleChildScrollView` without constraints | `CustomScrollView` with `SliverList` |
| Calling API in `build()` | Providers with `ref.watch` |
| `setState` for shared state | Riverpod `StateNotifier` |
| New overlay per message | Reuse `showModalBottomSheet` |
| Parsing response in widget | `ResponseParser` util called in provider |

---

## What "Connected Flow" Means

```
User types: "How does login work?"
        ↓
ChatProvider._sendMessage("How does login work?")
        ↓
CommandParser.parse() → CommandType.naturalLang, args: {query: "How does login work?"}
        ↓
RipClient.explain(query: "How does login work?", projectId: "flutter-app-123",
                  diagram: true, tree: true, deps: true)
        ↓
POST http://192.168.1.100:8000/explain
{ "query": "How does login work?", "project_id": "flutter-app-123",
  "diagram": true, "tree": true, "deps": true }
        ↓
Raw response text with Mermaid blocks, tree sections, tables
        ↓
ResponseParser.parse(raw, commandType: naturalLang)
→ [
    TextBlock("Here's how login works..."),
    WorkflowTreeBlock(nodes: [LoginScreen → AuthProvider → AuthRepo → API]),
    MermaidBlock(code: "graph LR\n  A→B..."),
    TableBlock(headers: [Symbol, Type, File], rows: [...]),
    FileListBlock(files: ["lib/screens/login.dart", "lib/providers/auth.dart"]),
    ImpactBlock(severity: "High", summary: "..."),
    SuggestionChipsBlock(chips: ["Show state flow", "Show impact", ...])
  ]
        ↓
Message.rip(blocks: [...]) added to chat state
        ↓
RipBubble renders all blocks in order
User sees exact UI from screenshot
```

---

## Definition of Done

- [ ] `flutter analyze` outputs 0 errors, 0 warnings
- [ ] `flutter build apk --debug` succeeds
- [ ] Setup screen connects to real RIP server at `http://<ip>:8000`
- [ ] Natural language query returns rich multi-block response
- [ ] `/search` command wired to GET /search
- [ ] `/explain` command wired to POST /explain with diagram+tree+deps
- [ ] `/trace` command wired to GET /trace/{symbol}
- [ ] `/impact` command wired to GET /impact/{symbol}
- [ ] `/architecture` command wired to GET /architecture
- [ ] `/index <url>` starts job + shows WS progress
- [ ] `@` switcher loads real projects from GET /projects/
- [ ] All 6 section cards (Workflow Tree, Mermaid, Dependencies, State Flow, Important Files, Impact) render from real API response
- [ ] Suggestion chips trigger new messages on tap
- [ ] Drawer shows real project list with status badges
- [ ] Chat history persists after app restart (SQLite)
- [ ] Error states render properly (no white screens)
- [ ] Dark theme matches screenshot exactly
