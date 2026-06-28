# RIP Flutter Mobile App — Complete Production Plan

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Framework** | Flutter 3.x (Dart) | You know it, fast rendering, single codebase |
| **State** | Riverpod 2.x | Type-safe, testable, no BuildContext dependency |
| **HTTP** | Dio | Interceptors for auth, retry, logging |
| **WebSocket** | web_socket_channel | Real-time indexing progress |
| **Routing** | GoRouter | Declarative, nested routes, deep linking |
| **Storage** | SharedPreferences | Server config, theme, simple key-value |
| **Database** | drift (SQLite) | Chat history persistence |
| **Markdown** | flutter_markdown | Render RIP responses |
| **Code Highlight** | flutter_highlight | Syntax highlighting in code blocks |
| **Mermaid** | flutter_mermaid or WebView | Render architecture diagrams |
| **Architecture** | Clean Architecture (data/domain/presentation) | Testable, maintainable |

---

## File Structure

```
flutter_app/
├── lib/
│   ├── main.dart                         # Entry point
│   ├── app.dart                          # MaterialApp + Riverpod + GoRouter
│   │
│   ├── core/
│   │   ├── constants.dart                # API URLs, defaults
│   │   ├── theme.dart                    # Light + dark theme
│   │   ├── exceptions.dart              # Custom exceptions
│   │   └── extensions.dart              # String, DateTime extensions
│   │
│   ├── data/
│   │   ├── models/
│   │   │   ├── project.dart              # ProjectModel
│   │   │   ├── message.dart              # ChatMessage, MessageType
│   │   │   ├── index_job.dart            # IndexJob, JobStatus
│   │   │   ├── search_result.dart        # SearchResult
│   │   │   ├── server_config.dart        # ServerConfig
│   │   │   └── rip_response.dart         # RipResponse (parsed)
│   │   │
│   │   ├── datasources/
│   │   │   ├── rip_api_client.dart       # Dio HTTP client
│   │   │   ├── rip_websocket_client.dart # WebSocket client
│   │   │   └── local_storage.dart        # SharedPreferences + SQLite
│   │   │
│   │   └── repositories/
│   │       ├── chat_repository.dart       # Chat history CRUD
│   │       ├── project_repository.dart    # Projects + indexing
│   │       ├── search_repository.dart     # Search + explain + trace
│   │       └── settings_repository.dart   # Server config + theme
│   │
│   ├── domain/
│   │   ├── enums/
│   │   │   ├── message_type.dart          # text, tree, mermaid, table, code, error
│   │   │   └── job_status.dart            # pending, cloning, indexing, complete, failed
│   │   │
│   │   └── usecases/
│   │       ├── send_message.dart          # Process user input → RIP command
│   │       ├── index_repository.dart      # Start git indexing
│   │       ├── search_codebase.dart       # Hybrid search
│   │       ├── explain_topic.dart         # Architecture explanation
│   │       └── switch_project.dart        # Change active project
│   │
│   ├── presentation/
│   │   ├── providers/
│   │   │   ├── chat_provider.dart         # ChatStateNotifier
│   │   │   ├── project_provider.dart      # ProjectStateNotifier
│   │   │   ├── settings_provider.dart     # SettingsStateNotifier
│   │   │   ├── index_provider.dart        # IndexStateNotifier
│   │   │   └── connection_provider.dart   # Server connection state
│   │   │
│   │   ├── screens/
│   │   │   ├── chat_screen.dart           # Main chat
│   │   │   ├── setup_screen.dart          # First-run server config
│   │   │   └── splash_screen.dart         # Loading + auto-connect
│   │   │
│   │   ├── widgets/
│   │   │   ├── chat/
│   │   │   │   ├── chat_bubble.dart       # Single message bubble
│   │   │   │   ├── user_message.dart      # User message style
│   │   │   │   ├── rip_message.dart       # RIP response style
│   │   │   │   ├── typing_indicator.dart  # Streaming indicator
│   │   │   │   └── suggestion_chips.dart  # Follow-up suggestions
│   │   │   │
│   │   │   ├── rich_content/
│   │   │   │   ├── tree_view.dart         # Workflow tree
│   │   │   │   ├── mermaid_view.dart      # Mermaid diagram
│   │   │   │   ├── table_view.dart        # Dependency table
│   │   │   │   ├── code_block.dart        # Syntax highlighted code
│   │   │   │   └── file_reference.dart    # Tappable file path
│   │   │   │
│   │   │   ├── overlays/
│   │   │   │   ├── command_palette.dart   # / slash commands
│   │   │   │   ├── project_switcher.dart  # @ project selector
│   │   │   │   └── add_repo_sheet.dart    # Add Git repo bottom sheet
│   │   │   │
│   │   │   ├── sidebar/
│   │   │   │   ├── app_drawer.dart        # Navigation drawer
│   │   │   │   ├── project_list.dart      # Projects in drawer
│   │   │   │   └── settings_section.dart  # Server config in drawer
│   │   │   │
│   │   │   └── common/
│   │   │       ├── status_badge.dart      # Indexed/Indexing/Failed
│   │   │       ├── progress_bar.dart      # Indexing progress
│   │   │       └── error_banner.dart      # Connection/auth errors
│   │   │
│   │   └── router/
│   │       └── app_router.dart            # GoRouter config
│   │
│   └── utils/
│       ├── markdown_parser.dart           # Markdown → Widget
│       ├── command_parser.dart            # Parse /commands and @mentions
│       └── date_formatter.dart            # Relative timestamps
│
├── pubspec.yaml
├── analysis_options.yaml
└── android/
```

---

## Riverpod Providers

```dart
// Settings
final serverUrlProvider = StateProvider<String>((ref) => '');
final apiKeyProvider = StateProvider<String>((ref) => '');
final themeModeProvider = StateProvider<ThemeMode>((ref) => ThemeMode.system);

// Connection
final connectionProvider = StateNotifierProvider<ConnectionNotifier, ConnectionState>((ref) {
  return ConnectionNotifier(ref.read(serverUrlProvider), ref.read(apiKeyProvider));
});

// Projects
final projectListProvider = StateNotifierProvider<ProjectListNotifier, AsyncValue<List<ProjectModel>>>((ref) {
  return ProjectListNotifier(ref.read(serverUrlProvider), ref.read(apiKeyProvider));
});

final activeProjectProvider = StateProvider<ProjectModel?>((ref) => null);

// Chat
final chatHistoryProvider = StateNotifierProvider<ChatNotifier, List<ChatMessage>>((ref) {
  return ChatNotifier();
});

// Indexing
final indexJobsProvider = StateNotifierProvider<IndexNotifier, Map<String, IndexJob>>((ref) {
  return IndexNotifier();
});

// API Client (singleton)
final apiClientProvider = Provider<RipApiClient>((ref) {
  return RipApiClient(
    baseUrl: ref.watch(serverUrlProvider),
    apiKey: ref.watch(apiKeyProvider),
  );
});
```

---

## GoRouter Configuration

```dart
final appRouter = GoRouter(
  initialLocation: '/splash',
  routes: [
    GoRoute(
      path: '/splash',
      builder: (context, state) => const SplashScreen(),
    ),
    GoRoute(
      path: '/setup',
      builder: (context, state) => const SetupScreen(),
    ),
    GoRoute(
      path: '/chat',
      builder: (context, state) => const ChatScreen(),
      routes: [
        // Nested routes accessible from chat context
        GoRoute(
          path: 'search',
          builder: (context, state) => const ChatScreen(initialCommand: '/search'),
        ),
      ],
    ),
  ],
);
```

**Navigation flow**:
- First launch (no saved config) → `/setup`
- Has saved config → `/splash` (try connect) → `/chat`
- `/chat` is the main screen. Everything else (search, explain, trace) happens IN the chat via commands, not separate routes.

---

## Chat Screen — The Only Screen That Matters

### Layout
```
┌─────────────────────────────┐
│  RIP Chat          ☰ [@]   │  ← AppBar: title, drawer, project indicator
├─────────────────────────────┤
│                             │
│  ┌─────────────────────────┐│
│  │ 🤖 RIP                  ││
│  │ Here's the workflow...  ││  ← Chat messages (ListView)
│  │ ┌─────────────────────┐ ││
│  │ │ 🌳 Workflow Tree     │ ││  ← Rich content inline
│  │ │ LoginScreen          │ ││
│  │ │  → AuthProvider      │ ││
│  │ │    → AuthRepo        │ ││
│  │ └─────────────────────┘ ││
│  │                         ││
│  │ [Trace] [Impact] [Files]││  ← Suggestion chips
│  └─────────────────────────┘│
│                             │
│  ┌─────────────────────────┐│
│  │ 🧑 You                  ││
│  │ What depends on it?     ││  ← User message
│  └─────────────────────────┘│
│                             │
├─────────────────────────────┤
│  ┌─────────────────────────┐│
│  │ Type / for commands...  ││  ← Input bar
│  │                    [→]  ││
│  └─────────────────────────┘│
└─────────────────────────────┘
```

### Message Types (Rendered Differently)

| Type | Widget | When |
|------|--------|------|
| `text` | Markdown body | Default response |
| `tree` | `TreeView` (indented, expandable) | Workflow chains |
| `mermaid` | `MermaidView` (WebView or cached image) | Architecture diagrams |
| `table` | `TableView` (horizontally scrollable DataTable) | Dependencies, metrics |
| `code` | `CodeBlock` (highlighted + copy button) | Source code snippets |
| `file` | `FileReference` (tappable → shows path, preview) | File references |
| `suggestion` | `SuggestionChips` (row of tappable chips) | Follow-up actions |
| `progress` | `ProgressBar` (animated) | Indexing status |
| `error` | `ErrorBanner` (red, with retry) | Failures |

---

## Command System

### Slash Commands (`/`)

Typing `/` in the input bar shows a bottom sheet overlay:

| Command | Parameters | API Call |
|---------|-----------|----------|
| `/search <query>` | query (required) | `GET /search?q=&project_id=` |
| `/explain <topic>` | topic (required) | `POST /explain` |
| `/trace <symbol>` | symbol (required) | `GET /trace/{symbol}` |
| `/impact <symbol>` | symbol (required) | `GET /impact/{symbol}` |
| `/architecture` | none | `GET /architecture` |
| `/metrics` | module (optional) | `GET /metrics` |
| `/onboard` | none | `GET /onboard` |
| `/dependencies <file>` | file (required) | `GET /dependencies?file=` |
| `/index <url>` | git_url (required) | `POST /git/index` |
| `/projects` | none | `GET /projects` |
| `/dead-code` | none | `GET /dead-code` |

**How it works**:
1. User types `/`
2. Overlay shows all commands with descriptions
3. User selects or types command name
4. Overlay shows required parameters with hints
5. User fills parameters and sends
6. Message appears in chat as user message: "`/search authentication flow`"
7. RIP responds inline

### Project Context (`@`)

Typing `@` shows a project switcher overlay:
- Lists all indexed projects
- Shows: name, language, files count, last indexed
- Tap to switch active project
- Chat header updates to show current project
- All subsequent `/commands` use this project

---

## Sidebar (Navigation Drawer)

```
┌─────────────────────────┐
│  🏠 RIP                  │
│  ─────────────────────── │
│  📁 Projects             │
│  ├─ flutter-app    ✅    │
│  ├─ payment-api    ✅    │
│  └─ auth-service   🔄    │
│  ─────────────────────── │
│  ➕ Add Repository       │
│  ─────────────────────── │
│  💬 Chat History         │
│  ├─ Today                │
│  │  ├─ "How login..."    │
│  │  └─ "Trace Auth..."   │
│  ├─ Yesterday            │
│  │  └─ "Architecture"    │
│  ─────────────────────── │
│  ⚙️  Settings             │
│  │  Server: 192.168...   │
│  │  Theme: Dark          │
│  ─────────────────────── │
│  ℹ️  About               │
└─────────────────────────┘
```

---

## Data Flow

```
User types "/search auth flow"
        │
        ▼
┌───────────────────┐
│ CommandParser     │  ← Parses /command and arguments
│ → command: search │
│ → args: auth flow │
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ ChatProvider      │  ← Adds user message to state
│ .sendCommand()    │  ← Adds pending RIP message
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ RipApiClient      │  ← GET /search?q=auth+flow&project_id=abc
│ .search()         │
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ ChatProvider      │  ← Receives response
│ .onResponse()     │  ← Parses RipResponse (text, tree, mermaid, table)
│                   │  ← Updates RIP message with rich content
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ ChatScreen        │  ← Rebuilds ListView
│                   │  ← User sees formatted response
└───────────────────┘
```

---

## pubspec.yaml Dependencies

```yaml
dependencies:
  flutter:
    sdk: flutter
  
  # State Management
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0
  
  # HTTP
  dio: ^5.4.0
  
  # WebSocket
  web_socket_channel: ^2.4.0
  
  # Routing
  go_router: ^14.0.0
  
  # Storage
  shared_preferences: ^2.2.0
  drift: ^2.16.0
  sqlite3_flutter_libs: ^0.5.0
  
  # UI
  flutter_markdown: ^0.7.0
  flutter_highlight: ^0.7.0
  google_fonts: ^6.1.0
  
  # Utilities
  uuid: ^4.3.0
  intl: ^0.19.0
  equatable: ^2.0.5
  freezed_annotation: ^2.4.0
  json_annotation: ^4.8.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  build_runner: ^2.4.0
  freezed: ^2.4.0
  json_serializable: ^6.7.0
  riverpod_generator: ^2.4.0
  drift_dev: ^2.16.0
  flutter_lints: ^4.0.0
```

---

## Build Order

### Week 1: Foundation
1. Flutter project setup + pubspec.yaml
2. Theme (light + dark)
3. GoRouter config
4. Riverpod providers (settings, connection)
5. RipApiClient (Dio + interceptors)
6. Setup screen (server URL + API key + test connection)

### Week 2: Chat Core
7. Chat screen layout (ListView + input bar)
8. ChatProvider (send message, receive response)
9. Message models (text, tree, mermaid, table, code)
10. Chat bubbles (user + RIP styles)
11. Markdown rendering in chat
12. Local chat history persistence (SQLite)

### Week 3: Commands + Rich Content
13. Command parser + overlay (`/` commands)
14. Project switcher (`@` overlay)
15. TreeView widget
16. MermaidView widget
17. TableView widget
18. CodeBlock widget
19. SuggestionChips widget

### Week 4: Projects + Sidebar
20. Sidebar/navigation drawer
21. Project list in drawer
22. Add Repository bottom sheet
23. WebSocket indexing progress
24. Error handling (all states)
25. Polish + testing

---

## Error States Every Screen Must Handle

| State | Widget |
|-------|--------|
| **Loading** | Shimmer placeholder or CircularProgressIndicator |
| **Empty** | Illustration + "No projects yet. Add one to get started." |
| **Error** | ErrorBanner with message + retry button |
| **Offline** | "Cannot connect to server. Check your connection." |
| **Unauthorized** | "Invalid API key. Update in settings." |

---

**This is a complete production plan. Every screen, every state, every widget is specified. The Flutter developer can build this without asking a single clarification question.****PROMPT FOR AGENT:**

Build the RIP Flutter mobile app. It should feel like ChatGPT/Claude mobile — a single chat-first interface where every RIP operation happens through natural conversation. No complex navigation. No form-heavy screens. Just chat.

---

## Core UX Principle

The app is a chat interface. The user types what they want. RIP figures out the rest. There is no "search screen" separate from "explain screen" — everything is one conversation.

---

## What the App Must Have

### 1. Single Chat Screen (Main)

This is the primary screen. User opens the app and sees:

- **Conversation history**: Messages bubble-style (user on right, RIP on left)
- **Rich responses**: RIP returns trees, Mermaid diagrams, tables, code blocks, dependency graphs — all rendered inline
- **Command chips**: Below each RIP response, tappable suggestions like "Trace this", "Show dependencies", "What depends on this?"
- **Input bar at bottom**: Text field with send button. Supports plain text and slash commands
- **Streaming text**: When RIP is generating an explanation, text appears word-by-word like ChatGPT
- **Context awareness**: User can ask follow-up "What depends on it?" and RIP knows what "it" is from the last response

### 2. Slash Commands (`/`)

Typing `/` opens a command palette overlay:

- `/search <query>` — Semantic search across indexed codebase
- `/explain <topic>` — Architecture explanation with diagram
- `/trace <symbol>` — Call chain tracing
- `/impact <symbol>` — Dependency impact analysis
- `/architecture` — Module/service architecture view
- `/metrics` — Coupling, churn, risk metrics
- `/onboard` — Repository overview for new developers
- `/dependencies <file>` — File-level import/dependency view
- `/index <git-url>` — Index a new repository from Git URL
- `/projects` — List all indexed repositories
- `/switch <project>` — Switch active project context

Each command has auto-complete. The command palette shows description and required parameters.

### 3. Project Context (`@`)

Typing `@` shows a project switcher overlay:

- Lists all indexed repositories
- Shows project name, language, file count, last indexed date
- Tapping switches the active project
- Chat header shows current project
- All subsequent queries are scoped to that project

### 4. Sidebar (Hamburger or Swipe)

Accessible from the chat header. Contains:

- **User info**: Server connection status, API key status
- **Server config**: URL field, API key field, test connection button
- **Active project**: Currently selected project with change option
- **All projects**: Scrollable list with status indicators (indexed, indexing, failed)
- **Add repository**: Button that opens a bottom sheet with Git URL + project name fields
- **Indexing progress**: Live progress bar when a repo is being indexed
- **Chat history**: List of previous conversations (persisted locally)
- **New chat**: Button to start fresh conversation
- **Settings**: Theme toggle (light/dark/system), clear cache, about

### 5. Rich Response Rendering

When RIP responds, the chat bubble renders:

- **Plain text**: Markdown with syntax highlighting
- **Trees**: Indented workflow trees (expandable/collapsible nodes)
- **Mermaid diagrams**: Rendered as images inline (use mermaid server or local renderer)
- **Tables**: Swipeable horizontally on mobile
- **Code blocks**: With syntax highlighting and copy button
- **File references**: Tappable — shows file path, line numbers, code preview
- **Suggestions**: Chip-style follow-up questions at the bottom of each response
- **Status indicators**: During indexing, shows live progress bar with file count

### 6. Indexing Flow

When user adds a repository:

1. User types `/index https://github.com/user/repo.git` or uses Add Repository sheet
2. RIP returns a message: "Cloning repository..."
3. Progress updates appear inline in the chat as streaming messages
4. When complete: "Indexed 2,147 entities across 569 files. Ask me anything."
5. Project automatically becomes active context

### 7. Error Handling

- **Server unreachable**: Red banner "Cannot connect to RIP server at [url]. Check settings."
- **API key invalid**: "Authentication failed. Update your API key in settings."
- **Indexing failed**: Shows error message from server with retry option
- **No project selected**: "Select a project to search. Type @ to see available projects."
- **Empty results**: "No results found. Try a different query or check if the project is indexed."

### 8. Offline/State Persistence

- **Chat history**: Saved locally (SQLite or shared preferences)
- **Server config**: Persisted across app restarts
- **Active project**: Remembered between sessions
- **Theme preference**: Saved

### 9. Authentication

- Server URL and API key configured in settings/setup
- First launch: Show setup screen (server URL + API key)
- Test connection button validates before saving
- API key sent as `Authorization: Bearer <key>` header

---

## Technical Requirements

- **State management**: Riverpod (consistent with Flutter ecosystem)
- **HTTP client**: Dio with interceptors for auth and error handling
- **WebSocket**: For live indexing progress
- **Local storage**: SharedPreferences or SQLite for chat history and config
- **Mermaid rendering**: Use `flutter_mermaid` or render via webview
- **Code highlighting**: `flutter_highlight` or similar
- **Architecture**: Clean separation — API client layer, provider layer, UI layer
- **Target**: Android first, iOS compatible but not required for Phase 2

---

## What NOT to Build

- No user accounts or multi-user authentication (API keys only)
- No push notifications
- No code editing
- No CI/CD integration
- No repository comparison
- No billing or usage limits
- No file picker or share sheet
- No offline indexing (requires server connection)
- No iOS-specific configuration for this phase

---

## File Structure

```
flutter_app/
├── lib/
│   ├── main.dart                    # App entry point
│   ├── app.dart                     # MaterialApp + theme + router
│   ├── config/
│   │   └── theme.dart               # Light/dark theme
│   ├── models/
│   │   ├── project.dart             # Project model
│   │   ├── message.dart             # Chat message model
│   │   ├── search_result.dart       # Search result model
│   │   └── index_job.dart           # Indexing job model
│   ├── services/
│   │   ├── api_client.dart          # RIP REST API client
│   │   ├── websocket_client.dart    # WebSocket for progress
│   │   └── storage_service.dart     # Local persistence
│   ├── providers/
│   │   ├── chat_provider.dart       # Conversation state
│   │   ├── project_provider.dart    # Projects + active project
│   │   ├── settings_provider.dart   # Server config
│   │   └── index_provider.dart      # Indexing jobs state
│   ├── screens/
│   │   ├── chat_screen.dart         # Main chat interface
│   │   ├── setup_screen.dart        # First-run server config
│   │   └── sidebar_screen.dart      # Navigation drawer
│   ├── widgets/
│   │   ├── chat_bubble.dart         # Message bubble
│   │   ├── command_palette.dart     # Slash command overlay
│   │   ├── project_switcher.dart    # @ project overlay
│   │   ├── rich_response.dart       # Renders trees, tables, mermaid
│   │   ├── indexing_progress.dart   # Live progress bar
│   │   ├── add_repo_sheet.dart      # Bottom sheet for git URL
│   │   └── suggestion_chips.dart    # Follow-up chips
│   └── utils/
│       ├── markdown_parser.dart     # Markdown to widgets
│       └── constants.dart           # API paths, defaults
├── pubspec.yaml
└── android/
    └── (Android config)
```

---

**Build this as a production chat app, not a demo.** Every screen should handle loading, empty, error, and success states. Every action should feel responsive. The chat should feel like talking to an expert who has the entire codebase memorized.