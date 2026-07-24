# RIP App — Comprehensive Screen-by-Screen Design POV Analysis

## Executive Summary & Design Architecture

The **RIP (Repository Intelligence Platform)** mobile app is a state-of-the-art Flutter client designed for deep code analysis, autonomous AI agent execution, MCP integrations, and visual workflow building. 

### Design Architecture & System Foundations
* **Theme System**: Centrally defined via `AppTheme` (`lib/core/theme.dart`) with `Material 3` design, Google Fonts (`Inter`), rounded corner cards (`borderRadius: 12`), and structured inputs.
* **Design Tokens**: `AppColors` (`lib/core/design/app_colors.dart`) defines a sleek dark-mode palette:
  * Backgrounds: `#0D0D0D` (Canvas), `#161616` (Surface), `#1E1E1E` (Surface Variant), `#2A2A2A` (Borders).
  * Primary Brand: `#7C3AED` (Deep Violet / Purple Accent), `#2E1B4E` (Primary Container), `#E0D7FA` (On Primary Container).
  * Status & Cues: `#22C55E` (Success/Green), `#F59E0B` (Warning/Amber), `#EF4444` (Error/Red), `#3B82F6` (Info/Blue).
* **Visual Signature**: Modern dark-mode aesthetic, glassmorphism overlays (frosted glass blur headers and floating composers), smooth haptic feedback (`HapticFeedback`), and node-based canvas rendering.

---

## Screen-by-Screen Design Breakdown

---

### 1. Splash Screen (`splash_screen.dart`)
* **Purpose**: Application launch, initialization of settings, active project loading, and connectivity checking.
* **Visual Layout & Structure**:
  * Centered vertical linear layout (`Column`).
  * 180×180 App Icon with `BorderRadius.circular(24)`.
  * Bold headline typography for "RIP" followed by subtitle "Repository Intelligence Platform".
  * Standard `CircularProgressIndicator` at the bottom.
* **Design Assessment**:
  * **Strengths**: Clean, centered branding focus with smooth initialization logic to automatically route users to `/chat` or `/setup`.
  * **Opportunities**: Could incorporate a subtle logo pulse/scale animation or a custom indeterminate linear progress bar matching the brand primary violet accent (`#7C3AED`) instead of standard circular spinner.

---

### 2. Setup Screen (`setup_screen.dart`)
* **Purpose**: First-time onboarding, Gateway server connection setup, API key entry, and default token budget configuration.
* **Visual Layout & Structure**:
  * Form layout inside `SingleChildScrollView` with 24px padding.
  * Prominent logo image (120×120) with header text.
  * Structured input fields with prefix icons (`Icons.link`, `Icons.key`, `Icons.admin_panel_settings_outlined`, `Icons.speed_rounded`, `Icons.pie_chart_outline_rounded`).
  * Horizontal input pairing (`Row` with `Expanded`) for Token budget & Overhead reserve %.
  * High-visibility error container (`errorContainer` color scheme) for diagnostic feedback during connection failures.
* **Design Assessment**:
  * **Strengths**: Excellent icon association per field, intuitive grouping of server connection vs token allocation parameters.
  * **Opportunities**: Grouping fields into distinct visual cards (e.g. *Server Credentials* card and *Gateway Token Policy* card) would improve visual scanability compared to a single continuous form stack.

---

### 3. Workspace Dashboard (`workspace_dashboard.dart`)
* **Purpose**: Overview of active project statistics, token consumption metrics, AI suggestions, and recent activity logs.
* **Visual Layout & Structure**:
  * Dynamic list with `RefreshIndicator` support.
  * `_ProjectHeader`: Card showcasing active project name, file count, and entity count with a violet container avatar.
  * `_MetricsRow`: 3 mini-cards (`Tokens Used`, `Saved %`, `Budget`) displaying stat counters with color-coded status (green for positive savings).
  * `_SuggestionsList`: Light-tinted suggestion cards with bulb icons (`Icons.lightbulb_outline`).
  * `_RecentActivityList`: Timeline-like list tiles with status indicators (green check for completed, orange sync for in-progress).
  * Empty state (`_EmptyState`): Dedicated graphic view with quick action button ("Open Chat") when no project is selected.
* **Design Assessment**:
  * **Strengths**: Strong dashboard scannability, compact metric cards, and clean status indicators.
  * **Opportunities**: The `_SuggestionsList` uses hardcoded `Colors.amber.shade50`, which creates harsh contrast in Dark Theme mode. Adapting this to `Theme.of(context).colorScheme` or `AppColors` would ensure theme consistency.

---

### 4. Chat Screen (`chat_screen.dart`)
* **Purpose**: Primary conversational AI workspace, live stream response viewer, workflow trigger modal, slash command auto-complete, and project context indicator.
* **Visual Layout & Structure**:
  * **Floating Glass Header (`_FloatingHeader`)**: Scroll-linked gradient veil (`_headerT` lerp interpolation), app title, active chat session title, drawer toggle, settings, and new chat quick actions.
  * **Project Context Card (`_ProjectContextCard`)**: Dark surface banner displaying file count, entity count, primary languages, and relative indexed time pills.
  * **Message Stream (`_MessageList`)**: Smooth entrance animations (`TweenAnimationBuilder` staggered opacity and translation) rendering `ChatBubble` components.
  * **Floating Composer (`_FloatingComposer`)**: Rounded glass container (`composerRadius` / `composerExpandedRadius`) featuring slash-command detector (`/`), project switcher (`@`), busy indicator bar, send button, and stop button.
  * **Workflow Attachment Bottom Sheet**: Slide-up picker enabling direct insertion of visual canvas workflows (`/workflow <id>`).
* **Design Assessment**:
  * **Strengths**: **Flagship design quality.** Exceptional use of glassmorphic translucency, haptic feedback, subtle animations, and multi-tier command interaction UX.

---

### 5. Visual Workflows Canvas (`workflows_screen.dart`)
* **Purpose**: Node-based visual graph builder for multi-step AI pipelines, live step execution monitor, block palette, wire connector, and minimap navigation.
* **Visual Layout & Structure**:
  * **Infinite Canvas (`_Canvas`)**: Grid backdrop toggle, node blocks with status badges, interactive bezier curve wires (`_WirePainter`), and multi-block selection boxes (`_SelectionToolbar`).
  * **Floating Header & Toolbar**: Workflow switcher, undo/redo stack triggers, grid/minimap/snap controls, wire-mode toggle (`_wireMode`), and auto-layout action.
  * **Docking Controls (`_Dock`)**: Floating bottom-right action bar for adding blocks, publishing, running, copy/paste, import/export JSON, and duplicating workflows.
  * **Live Execution Panel (`_RunPanel`)**: Bottom overlay rendering live step progress, interactive question input for agent pauses, and human-in-the-loop approval/rejection triggers.
  * **Minimap (`_Minimap`)**: Interactive radar view positioned at bottom-left providing real-time spatial positioning of canvas nodes.
* **Design Assessment**:
  * **Strengths**: **Desktop-grade canvas interface in mobile Flutter.** Rich interactive wire connection flow (with input port picker sheet), smooth pan/zoom, and comprehensive undo/redo history stack.

---

### 6. Agent Runs Screen (`agent_runs_screen.dart`)
* **Purpose**: Historical & real-time monitoring of autonomous background agent tasks and pending tool authorization requests.
* **Visual Layout & Structure**:
  * Card-based list displaying run query, status indicator (amber lock for approval needed, green check for completed, orange sync for running), and trailing chevron.
  * **Detail Bottom Sheet (`_AgentRunDetailSheet`)**: `DraggableScrollableSheet` containing run metadata, live execution trace step list (`PipelineStepList`), and approval prompt (`_ApprovalCard`).
* **Design Assessment**:
  * **Strengths**: Highly clear human-in-the-loop approval UX (`Approve` / `Reject` buttons with amber warning container), ensuring developers maintain control over execution tools.

---

### 7. Gateway Sources & Integrations Screen (`gateway_sources_screen.dart`)
* **Purpose**: Account integrations management (GitHub, Jira, Slack), project-level MCP server attachment, and tool capability discovery.
* **Visual Layout & Structure**:
  * **Active Project Panel (`_ProjectPanel`)**: Header card showing connected project status and quick "Add repo" action.
  * **Account Integrations**: Cards for GitHub/Jira/Slack with OAuth status chips (`_StateChip`), account labels, and action buttons (`Connect`, `Use token`, `Projects`, `Disconnect`).
  * **Project Custom MCP Tools (`_CustomToolsSection`)**: List of custom MCP endpoints with credential management, health test actions, and expandable capability tool chips (`_SourceToolChip`).
  * **Modal Bottom Sheets**: Allocation sheet (`_AllocationSheet`) for project assignment and MCP creation form (`_CustomMcpSheet`).
* **Design Assessment**:
  * **Strengths**: Complete end-to-end integration management UI with rich status feedback, deep linking support (`AppLinks`), and capability tool inspection.

---

### 8. Gateway Activity Telemetry Screen (`gateway_activity_screen.dart`)
* **Purpose**: High-level real-time gateway performance metrics and session tracking.
* **Visual Layout & Structure**:
  * Metric Chips Grid (`_Metric`): Active sessions, total sessions, tokens retrieved, tokens delivered, and active conflicts.
  * Session List: Dense list tiles displaying task descriptions, session intent classifications, and execution statuses.
* **Design Assessment**:
  * **Strengths**: Fast scannability of operational metrics.
  * **Opportunities**: Metrics chips could be upgraded to metric cards (similar to Workspace Dashboard) to create consistent visual weight.

---

### 9. Gateway Audit Log Screen (`gateway_audit_screen.dart`)
* **Purpose**: Security access log viewer detailing access control decisions made by the gateway.
* **Visual Layout & Structure**:
  * `ListView.separated` with dense `ListTile` items.
  * Status icons: Green `verified_user_rounded` icon for allowed access, amber `block_rounded` for blocked actions.
  * Subtitle text showing role, source, reason, or session ID.
* **Design Assessment**:
  * **Strengths**: Clean, compact 3-line layout for security audit review.
  * **Opportunities**: Addition of a filter bar (Filter by Role, Allowed/Blocked, or Source) for faster security triage.

---

### 10. LLM Settings Screen (`llm_settings_screen.dart`)
* **Purpose**: LLM model configuration management (OpenAI, Anthropic, Gemini, Ollama, custom providers).
* **Visual Layout & Structure**:
  * Model Config Cards: Displaying provider name, model identifier, API key status badge (green key icon when set, orange when missing), and custom badge.
  * Popup Menu: Edit and Delete actions for custom configs.
  * **Add/Edit Sheet**: Modal bottom sheet with text fields for Name, Provider, Model, API Key, and Base URL.
  * Empty State: Psychology icon illustration with helpful descriptive caption.
* **Design Assessment**:
  * **Strengths**: Excellent empty state representation and intuitive modal form flow for adding local or cloud LLM instances.

---

### 11. MCP Export Screen (`mcp_export_screen.dart`)
* **Purpose**: Generates ready-to-use JSON configuration snippet for external MCP client tools (e.g. Claude Desktop, VS Code).
* **Visual Layout & Structure**:
  * Formatted JSON block using `SelectableText` in custom monospace font (`fontFamily: 'monospace'`).
  * Prominent `FilledButton.icon` for one-tap copy to system clipboard with SnackBar confirmation.
* **Design Assessment**:
  * **Strengths**: Hyper-focused utility screen with single-tap export functionality.

---

### 12. Sandbox & Sandbox Setup Screens (`sandbox_screen.dart`, `sandbox_setup_screen.dart`)
* **Purpose**: Isolated container environment selection, active sandbox status tracking, and embedded terminal console interaction.
* **Visual Layout & Structure**:
  * **Cyber Dark Theme Palette**: Custom background `#0F0F23` and header background `#16213E`.
  * **Environment Picker (`EnvironmentPicker`)**: Template selection grid (Docker, Python, Node, Go, Rust).
  * **Status Bar (`SandboxStatusBar`)**: Container state, resource indicators, and quick snapshot actions.
  * **Terminal View (`TerminalView`)**: Interactive CLI terminal output window.
* **Design Assessment**:
  * **Strengths**: Theme intentionally switches to a deep cyber-navy color scheme (`#0F0F23`), providing clear visual context that the user has entered a sandboxed terminal environment.

---

## Design System Summary & Comparative Matrix

| Screen Name | Visual Style / Surface | Key Design Feature | UX Highlights | Theme Consistency |
| :--- | :--- | :--- | :--- | :--- |
| **Splash Screen** | Minimal Centered | Brand Icon & Title | Auto-routing initialization | High |
| **Setup Screen** | Structured Form Stack | Input Field Prefix Icons | Real-time connection feedback | High |
| **Workspace Dashboard** | Card-based Dashboard | Stat Cards & Suggestions | Metric scannability, pull-to-refresh | Medium (Light Amber tint) |
| **Chat Screen** | Glassmorphism & Floating | Frosted Header & Composer | Haptics, slash commands, animation | High (Flagship) |
| **Workflows Screen** | Node Canvas & Dock | Interactive Graph & Wires | Pan/zoom, port picker, undo/redo | High (Desktop-grade) |
| **Agent Runs Screen** | Detail Sheet & Stream | Tool Approval Cards | Human-in-the-loop decision buttons | High |
| **Gateway Sources** | Sectioned Cards & Chips | Tool Capability Tags | Deep links, OAuth, token modal | High |
| **Gateway Activity** | Metrics Chips & List | Telemetry Chips | Real-time session monitoring | High |
| **Gateway Audit** | Dense Separated List | Color-coded Access Icons | Security event triage | High |
| **LLM Settings** | Card List with Badges | Provider & Key Status Chips | Modal bottom sheet editor | High |
| **MCP Export** | Monospace Code Box | One-tap Copy JSON | Clipboard integration feedback | High |
| **Sandbox Screen** | Cyber IDE Dark (`#0F0F23`)| Interactive Terminal View | Custom theme for isolated container | Intentional Divergence |

---

## Key Recommendations for Design Polish

1. **Unify Dashboard & Suggestion Card Tints**: Replace hardcoded `Colors.amber.shade50` in `workspace_dashboard.dart` with theme-aware container fills (`AppColors.primaryContainer` or `colorScheme.surfaceContainerHigh`) to maintain dark theme elegance.
2. **Upgrade Telemetry Chips in Gateway Activity**: Transition simple metric chips in `gateway_activity_screen.dart` to styled mini metric cards matching `_MiniCard` from `workspace_dashboard.dart`.
3. **Audit Log Filter Bar**: Add a row of quick filter chips (All, Allowed, Blocked) to `gateway_audit_screen.dart` to enhance usability during security analysis.
4. **Group Form Fields on Setup Screen**: Wrap connection inputs into two distinct `Card` sections (*Server Settings* and *Execution Defaults*) for better visual structure on wide screens.
