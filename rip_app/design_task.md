# RIP Application — Design System & Refactoring Task Directory

> **Design Goal Reference**: [ChatGPT Image Jul 24, 2026, 06_11_29 PM.png](file:///c:/Users/Dell/Downloads/RIP/rip_app/ChatGPT%20Image%20Jul%2024,%202026,%2006_11_29%20PM.png)  
> ![Master Design Goal Spec Sheet](file:///c:/Users/Dell/Downloads/RIP/rip_app/ChatGPT%20Image%20Jul%24%202026%2C%2006_11_29%20PM.png)
> 
> *The image above and `base_design.md` represent the target visual design system for all screens in RIP.*

---

## Executive Summary & Design Approach

The RIP application visual design system bridges two core functional surfaces:
1. **Sandbox / Execution Surface (Board A)**: File editor, terminal, package manager, execution logs, interactive REPL.
2. **Assistant / Dashboard Surface (Board B)**: AI Chat interface, agent runs, visual workflow builder, integration connectors, settings.

Both surfaces share a single canonical visual design language derived from `base_design.md` and the master reference spec (`ChatGPT Image Jul 24, 2026, 06_11_29 PM.png`).


### Core Design Rules
- **Color Discipline**: Primary purple (`#5F3ADD`) is strictly reserved for brand accents, primary buttons, active navigation, and mascot body. Green (`#22C55E`), amber (`#F59E0B`), red (`#EF4444`), and blue (`#3B82F6`) are used strictly for semantic status indicators (never decorative).
- **Surface Elevation**: App shell uses light background (`#FAFAFC`). Cards use solid white (`#FFFFFF`) with 1px border (`#ECEAF3`), 12px radius, flat at rest, and soft hover elevation on interactive cards only.
- **Dual Surface Theming**: Code/Terminal contexts (editor, console, logs, terminal) use dark `#1E1E2E` code background + JetBrains Mono. All other surfaces use clean light theme + Inter font.
- **Button Standards**: Pill radius (`BorderRadius.circular(9999)`). Primary = solid purple + white text; Secondary = white + 1px border; Destructive = solid/outlined red.
- **State-Driven Mascot System**: Single purple ghost mascot asset per screen max, tied strictly to real application state (e.g. `waving.png` for onboarding, `loading.png` for execution, `success.png` for completed tasks, `security_shield.png` for vulnerability risks).

---

## Task Progress Directory

### Phase 1: Core Design System Foundation & Tokens
- [x] **Design Tokens Definition (`app_colors.dart`)**
  - Brand: `primary` (`#5F3ADD`), `primaryDark` (`#5B3FE0`), `primaryContainer` (`#7857F8`), `primaryLight` (`#EDE9FE`), `gradient`
  - Surface: `background` (`#FAFAFC`), `surface` (`#FFFFFF`), `surfaceContainerHigh` (`#EBE4FF`), `border` (`#ECEAF3`)
  - Text: `textPrimary` (`#1B1730`), `textSecondary` (`#6B6580`), `textMuted` (`#8C86A0`)
  - Semantic: `success` (`#22C55E`), `warning` (`#F59E0B`), `danger` (`#EF4444`), `info` (`#3B82F6`)
  - Code: `codeBg` (`#1E1E2E`), `codeTextOutput` (`#22C55E`), `codeTextDefault` (`#E4E1EE`)
- [x] **Typography Scale (`app_text_styles.dart`)**
  - Added `statXl` (32px bold), `headlineLg` (20px semi), `headlineMd` (16px semi), `bodyMd` (14px regular), `bodyMdBold` (14px semi), `bodySm` (12px regular), `labelCaps` (10px bold uppercase), `codeSm` (JetBrains Mono 12px).
- [x] **Theme System Configuration (`app_theme.dart` & `theme.dart`)**
  - Configured `ripLightTheme` as default app scaffold background (`#FAFAFC`), white card theme (`#FFFFFF`, 12px radius, 1px border), pill buttons, and input fields. Consolidated legacy `lib/core/theme.dart`.

### Phase 2: Mascot Asset System
- [x] Registered `assets/mascot/` in `pubspec.yaml` for 40 PNG assets.
- [x] Created `RipMascotPose` enum mapping 40 pose PNG files.
- [x] Implemented `fromState()` pose resolver mapping screen states (`welcome`, `loading`, `success`, `error`, `thinking`, `coding`, `debugging`, `security`, `empty`) to poses.
- [x] Created `RipMascotWidget` with custom dimensions and fallback handling.

### Phase 3: Core Reusable UI Component Library (`lib/presentation/widgets/common/`)
- [x] **Centralized Icon System (`app_icons.dart`)**: Single point of icon definitions for navigation, actions, and tools.
- [x] **`RipButton`**: Primary, Secondary, Destructive pill buttons with loading and icon support.
- [x] **`RipCard`**: Standard white surface card (12px radius, 1px border, flat at rest, hover elevation).
- [x] **`RipTextField`**: Standardized input field with top label, 16px radius, and password visibility toggle.
- [x] **`RipStatusDot` & `RipStatusBadge`**: 8px filled circle + semantic color label status pills.


- [x] **`RipImpactCard`**: Finding/vulnerability card with 4px left accent bar, `labelCaps` tag, title, desc, and action link.
- [x] **`RipListRow`**: Standard file/package/log list row with hover bg (`#EDE9FE`).
- [x] **`RipProgressBar`**: Thin track rounded-full progress bar.
- [x] **`RipTraceRow`**: Pipeline trace step row with status dot, duration, and level indentation.
- [x] **`RipTopBar`**: Standard screen header bar (back icon, title, status, actions, avatar).
- [x] **`design.dart`**: Created single entry-point barrel export for design tokens and core widgets.
- [x] **Compatibility Fixes**: Supported `status` parameter in legacy `StatusBadge` widget for backward compatibility across screens.

---

## Checkpoints

### Checkpoint 1: Core Design System Foundation
- **Status**: **COMPLETED**
- **Artifacts Created/Refactored**:
  - `lib/core/design/app_colors.dart`
  - `lib/core/design/app_text_styles.dart`
  - `lib/core/design/app_theme.dart`
  - `lib/core/design/mascot_system.dart`
  - `lib/core/design/design.dart`
  - `lib/presentation/widgets/common/rip_button.dart`
  - `lib/presentation/widgets/common/rip_card.dart`
  - `lib/presentation/widgets/common/status_badge.dart`
  - `lib/presentation/widgets/common/rip_impact_card.dart`
  - `lib/presentation/widgets/common/rip_list_row.dart`
  - `lib/presentation/widgets/common/progress_bar.dart`
  - `lib/presentation/widgets/common/rip_trace_row.dart`
  - `lib/presentation/widgets/common/rip_top_bar.dart`
  - `lib/presentation/widgets/common/rip_mascot_widget.dart`
- **Validation**: Passed `flutter analyze` with 0 compilation errors.

---

### Checkpoint 2: Board A — Sandbox / Execution Surface Refactoring
- [ ] **A1. Project Workspace**: Standardize file list rows and run button.
- [ ] **A2. Code Output / Results**: Standardize dark `#1E1E2E` code output panel and `danger` stop button.
- [ ] **A3. Package Installer**: Refactor Installed/Available tab bar and list rows.
- [ ] **A4. File Editor**: Standardize dark code area coexist with top bar.
- [ ] **A5. Sandbox Status**: Refactor healthy/running hero mascot card and stat progress bars.
- [ ] **A6. Error Display**: Apply `danger` traceback block and `error.png` mascot.
- [ ] **A7. Terminal / Console**: Standardize dark terminal panel and command pill chips.
- [ ] **A8. Project Settings**: Unify list-row settings components.
- [ ] **A9. Package Installation Progress**: Refactor install progress modal and log output.
- [ ] **A10. File Creation**: Standardize new file modal dialog.
- [ ] **A11. Console (Interactive Python)**: Align REPL console styling with A7.
- [ ] **A12. Sandbox Logs**: Apply severity-coded status dots to event stream.

---

### Checkpoint 3: Board B — Assistant / Dashboard Surface Refactoring
- [x] **B1. Onboarding / Splash Screen (`splash_screen.dart`)**: Applied hero `waving.png` mascot, canonical typography, and progress indicator.
- [x] **B2. Server Connection (`setup_screen.dart`)**: Refactored to B2 spec sheet layout with state-driven mascot, `RipCard` configuration container, `RipButton.primary`, `RipTopBar`, and `RipImpactCard` error banner.
- [x] **B3. Chat Interface (`chat_screen.dart`, `rip_message.dart`, `user_message.dart`, `typing_indicator.dart`)**:
  - Full-width modern assistant response cards with `RipMascotWidget` avatar header.
  - Standardized user message pill bubbles (`#5F3ADD`).
  - Preserved floating AppBar layout with project selector and session title.
  - Upgraded action pills (Copy, Regenerate, Open workflow run) and typing indicators.


- [ ] **B4. Workspace Dashboard**: Apply greeting header, stat cards (`statXl`), and line chart accent.
- [ ] **B5. Agent Runs**: Refactor execution history list and live trace detail panel.
- [ ] **B6. Workflows (Builder)**: Align list, block picker, canvas diagram, and right inspector panel.
- [ ] **B7. Integrations / Sources**: Refactor integration card grid.
- [ ] **B8. Settings**: Standardize settings category list rows.
- [ ] **B9. Pipelines Trace (Expanded)**: Reuse `RipTraceRow` component.
- [ ] **B11. Mermaid Diagram**: Style generated diagrams with `surfaceContainerHigh` `#EBE4FF` fill.
- [ ] **B14. Command Palette**: Standardize `/` modal search overlay and kbd hints.

---

### Checkpoint 4: Final Design Checklist & System Audit
- [ ] Verify Section 6 checklist against all 28 screens.
- [ ] Verify light app shell `#FAFAFC` & white `#FFFFFF` 12px radius cards across entire application.
- [ ] Run full project compilation check (`flutter analyze`) and test suite.
