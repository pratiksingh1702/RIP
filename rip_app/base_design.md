---
name: rip-base-design
description: Single source of truth for RIP's visual design system. Merges brand tokens with a screen-by-screen breakdown of every existing screen. Read this before refactoring, generating, or editing ANY screen in the app — apply Section 1-6 tokens globally, then check the matching entry in Section 7 for that screen's specific layout/component rules.
mascot_assets_path: assets/mascot/*.png
---

# RIP — Base Design System

RIP is a purple, ghost-mascot-led AI developer assistant. It has two functional surfaces:
- **Sandbox/Execution surface** (file editor, terminal, packages, logs — "Board A")
- **Assistant/Dashboard surface** (chat, workflows, integrations — "Board B")

Both surfaces MUST share one design language. This doc is that language. Do not invent new colors, radii, spacing, or component shapes per-screen — everything below is reused, not reinvented.

---

## 1. Design Tokens (canonical — use these hex values everywhere)

```yaml
color:
  # Brand
  primary: '#5f3add'          # buttons, active nav, links, mascot body
  primary-dark: '#5B3FE0'      # hover/pressed
  primary-container: '#7857f8' # gradient end / lighter brand fill
  primary-light: '#EDE9FE'     # selected row bg, subtle chips
  gradient: 'linear-gradient(135deg, #8B7CF6, #6D4FE8)' # app icon, hero, celebratory panels only

  # Surface
  background: '#FAFAFC'        # page/app shell background
  surface: '#FFFFFF'           # cards, panels
  surface-container-high: '#ebe4ff'  # elevated purple-tinted surfaces (e.g. workspace dashboard header)
  border: '#ECEAF3'            # all card borders/dividers, 1px

  # Text
  text-primary: '#1B1730'      # headings, primary content, code
  text-secondary: '#6B6580'    # meta, timestamps, labels, placeholder text

  # Semantic (status ONLY — never decorative)
  success: '#22C55E'           # Connected, Running, Passed, Success
  warning: '#F59E0B'           # Partial, install-in-progress, warnings
  danger: '#EF4444'            # Failed, Error, High Impact, destructive actions
  info: '#3B82F6'              # GitHub/secondary integration accents, informational tags

  # Dark code surfaces (terminal, console, code editor bg)
  code-bg: '#1E1E2E'
  code-text-output: '#22C55E'  # stdout success lines
  code-text-default: '#E4E1EE'

typography:
  family-ui: Inter
  family-code: 'JetBrains Mono'
  stat-xl:      { size: 32px, weight: 700, lineHeight: 40px, letterSpacing: -0.02em }   # big numbers (2.4M, $12.45)
  headline-lg:  { size: 20px, weight: 600, lineHeight: 28px }                            # screen titles
  headline-md:  { size: 16px, weight: 600, lineHeight: 24px }                            # card titles
  body-md:      { size: 14px, weight: 400, lineHeight: 20px }                            # body text
  body-sm:      { size: 12px, weight: 400, lineHeight: 18px }                            # meta/secondary
  label-caps:   { size: 10px, weight: 700, lineHeight: 12px, letterSpacing: 0.05em }      # HIGH IMPACT tags
  code-sm:      { family: JetBrains Mono, size: 12px, weight: 400, lineHeight: 18px }     # code/terminal/logs

radius:
  sm: 4px
  DEFAULT: 8px
  card: 12px      # standard card radius everywhere
  lg: 16px
  full: 9999px    # buttons, pills, status badges

spacing:
  grid-margin: 24px
  grid-gutter: 16px
  card-gap: 20px
  section-padding: 32px
  stack-sm: 8px
  stack-md: 16px

elevation:
  rest: none                                  # cards are flat by default
  hover: '0 4px 12px rgba(28,24,49,0.06)'      # soft lift on hover/interaction only
```

**Non-negotiable rules:**
1. Purple = brand + primary action + mascot only. Never used for status.
2. Green/amber/red/blue = status only. Never decorative.
3. Every card: white bg, 1px `border`, `card` (12px) radius, no shadow at rest.
4. Every button: pill radius (`full`). Primary = solid purple + white text. Secondary = white + 1px border + `text-primary`. Destructive = solid or outlined red.
5. Status is always color **+ icon/label**, never color alone (colorblind-safe).
6. Code/terminal contexts (editor, console, logs, terminal) switch to `code-bg` dark surface + `JetBrains Mono`. Everything else stays light + `Inter`.

---

## 2. Typography Hierarchy Rules

- Page/screen title → `headline-lg`, `text-primary`
- Card/section title → `headline-md`, `text-primary`
- Stat/metric (Projects: 12, $12.45) → `stat-xl` number, `body-sm`/`text-secondary` label underneath
- Body copy, list item titles → `body-md`
- Timestamps, file sizes, helper text, breadcrumbs → `body-sm`, `text-secondary`
- Tag/badge text (HIGH IMPACT, status pills) → `label-caps`
- Anything inside a code/terminal/console panel → `code-sm`, `JetBrains Mono`

---

## 3. Layout Skeleton (reused across almost every screen)

```
┌─────────────┬────────────────────────────────────────┐
│             │  Top bar: [icon] Title   [status] [avatar] │
│  Left rail  ├────────────────────────────────────────┤
│  240–280px  │                                          │
│  nav        │  Main content (chat stream / card grid  │
│             │  / editor / terminal)                    │
│             │                                          │
│             ├────────────────────────────────────────┤
│             │  Optional right inspector 320–400px      │
└─────────────┴────────────────────────────────────────┘
```

- **Left rail**: persistent on Workspace, Chat, Dashboard, Agent Runs, Workflows, Integrations, Settings. NOT present on modal-like flows (Onboarding/Connect, full-screen Editor focus, Terminal-only view).
- **Top bar pattern**: back-arrow (if nested) + icon + title + right-aligned status/action + avatar. Identical structure on every sub-screen (Packages, File Editor, Sandbox Status, Terminal, Settings, etc).
- **12-col grid** for dashboard/stat card rows, 16-20px gutters.
- **Right inspector** (320-400px) only appears for block/detail editing (Workflow block editor).
- Mobile: left rail collapses to hamburger; grid reflows to single column.

---

## 4. Core Components (build once, reuse everywhere)

| Component | Spec |
|---|---|
| Primary button | Pill, solid `primary`, white text, `body-md` weight 600 |
| Secondary button | Pill, white bg, 1px `border`, `text-primary` |
| Destructive button | Pill, `danger` bg or `danger` outline |
| Status dot + label | 8px filled circle (semantic color) + `body-sm` label — "Connected", "Running", "Healthy" |
| Card | White, 1px `border`, `card` radius, no shadow at rest, hover shadow only if clickable |
| Impact/finding card | Card + 4px left accent bar in semantic color + `label-caps` tag (HIGH/MEDIUM/LOW) + title + 1-line desc + "View details →" |
| List row (files, packages, logs) | icon + title (`body-md`) + meta (`body-sm`, right or below) + consistent row height, hover bg = `primary-light` |
| Toggle switch | Standard iOS-style, `primary` when on |
| Progress bar | Thin, rounded-full track, `primary` or `warning` fill depending on context |
| Trace/log row | dot + step name (`code-sm` or `body-sm`) + indentation for nesting + duration right-aligned |
| Empty/success state | One mascot pose, centered, `headline-md` headline below, optional checklist |
| Command palette | Modal, search input top, `/command` + description rows, kbd hint right-aligned |
| Tab bar (e.g. Executions/Live Trace) | Underline-style active tab, `primary` underline + text, inactive = `text-secondary` |

---

## 5. Mascot System

Path: `assets/mascot/*.png` — 39 expression PNGs, flat purple body, white oval face, no outlines.

**Usage rule: one mascot per screen max, always tied to real state.** Never decorative, never repeated.

| Screen state | Use asset |
|---|---|
| App/onboarding branding | `waving.png` or `happy.png` |
| Any loading/in-progress panel | `loading.png` |
| Successful run / install / task complete | `success.png` or `celebrating.png` / `party.png` |
| Sandbox running & healthy | `happy.png` or `robot_mode.png` |
| Execution failed / crash | `error.png` |
| Security warning / risky finding | `warning.png` or `security_shield.png` |
| Chat "thinking"/generating | `thinking.png` |
| Actively writing/editing code | `coding.png` or `typing.png` |
| Debugging an error | `debugging.png` |
| Searching files/codebase | `searching.png` or `scanning.png` |
| Reviewing PR/diff | `reviewing.png` |
| Empty state (no chats/projects) | seated/`sleeping.png` or `idea.png` |
| Confused / ambiguous input | `confused.png` |
| Docs/reading content | `reading_docs.png` |
| Idle/meditating (no activity) | `meditating.png` or `coffee_break.png` |
| Celebration / milestone | `party.png`, `excited.png`, `thumbs_up.png` |

Never redraw the body per pose — accessories/expression only. Never use `error.png` or `warning.png` unless there's a genuine failure/risk on screen.

---

## 6. Refactor Checklist (apply to EVERY screen before shipping)

1. [ ] Background is `#FAFAFC`, cards are `#FFFFFF` with `#ECEAF3` 1px border, 12px radius
2. [ ] All primary actions are solid purple pill buttons; no purple used for status
3. [ ] All status indicators use color + label/icon, from the semantic palette only
4. [ ] Typography matches the scale in Section 2 — no ad-hoc font sizes
5. [ ] Code/terminal/log areas use dark `#1E1E2E` bg + JetBrains Mono
6. [ ] Left rail present unless screen is onboarding/modal/full-focus
7. [ ] Top bar follows icon + title + status/action + avatar pattern
8. [ ] Mascot (if present) matches actual screen state, one instance only
9. [ ] Spacing uses the 8/16/20/24/32 scale — nothing arbitrary
10. [ ] Buttons/cards/toggles are the shared components in Section 4, not new ones

---

## 7. Screen-by-Screen Reference

Use this section as your refactor punch list — one entry per screen, in the order to tackle them. Each entry lists: **purpose**, **key components used**, **mascot** (if any), and **refactor notes**.

### Board A — Sandbox / Execution Surface

**A1. Project Workspace**
- Purpose: home screen for a sandbox project — file list, run action, recent output feed.
- Components: left rail (Files list rows, "New File" secondary button), primary "Run main.py" button, "Recent Output" status rows with green dots.
- Mascot: none currently — could add small `happy.png` next to project name in header.
- Refactor notes: file rows need consistent icon-by-filetype system; status dots on recent output should use the shared status-dot component.

**A2. Code Output / Results**
- Purpose: shows stdout after running a script.
- Components: dark code panel (`code-bg`), status pill "Success" (green), action row (Clear/Copy/Share as secondary pill buttons), destructive "Stop Execution" as full-width danger button.
- Mascot: none — correct, execution output doesn't need one.
- Refactor notes: "Stop Execution" should use `danger` token, not a custom red; ensure output text uses `code-sm`.

**A3. Package Installer**
- Purpose: browse/manage installed vs available packages.
- Components: tab switch (Installed/Available), search input, list rows (name + version + "Latest" tag), primary "+ Install" and "Install New Package" buttons.
- Mascot: none.
- Refactor notes: version "Latest" tag should be `label-caps` in `text-secondary`, not styled as a status badge (it's informational, not semantic).

**A4. File Editor**
- Purpose: code editing view for a single file.
- Components: top bar (icon+filename+language, primary "Save" button), line-numbered code area (`code-sm`), bottom toolbar (Format secondary, Run primary), cursor position indicator (`Ln 14, Col 22`) in `text-secondary`.
- Mascot: none — keep editor focus-mode clean.
- Refactor notes: ensure the code area strictly uses `code-bg`/`code-sm` even though rest of app is light — this is the one screen where dark+light coexist by design.

**A5. Sandbox Status**
- Purpose: health/resource overview for the running sandbox.
- Components: centered mascot hero, status dot ("Running / Healthy"), stat rows (Uptime, Python Version, Disk, Memory) with progress bars, primary "View Details" button.
- Mascot: `happy.png` or `robot_mode.png` — matches "healthy/running" state. Currently a generic purple ghost illustration; replace with the actual asset from `assets/mascot/`.
- Refactor notes: this is a template for all "status hero" screens — reuse for Chat welcome and Success states too.

**A6. Error Display**
- Purpose: shows a failed execution traceback.
- Components: status pill "Error" (`danger`), traceback block in `code-bg`/`code-sm` with `danger`-colored highlight on the failing line, primary "Fix with AI" button, secondary "View Full Trace".
- Mascot: `error.png` — could sit next to "Execution Failed" title for warmth, currently absent.
- Refactor notes: keep traceback strictly monospace; line-highlight should use `danger` at low opacity as background, not full-saturation fill.

**A7. Terminal / Console**
- Purpose: raw shell access.
- Components: dark terminal panel, command input row, quick-command chips (ls, cd, python...) as small secondary pills.
- Mascot: none — full-focus utility screen, no left rail needed.
- Refactor notes: quick-command chips should use `body-sm`/pill-secondary style, not free-floating text.

**A8. Project Settings**
- Purpose: sandbox configuration actions.
- Components: list rows each with icon + title + description + chevron, destructive "Delete Sandbox" row styled in `danger`.
- Mascot: none.
- Refactor notes: standardize this as the canonical "settings list" component — reuse row style for Board B Settings screen too (currently they differ).

**A9. Package Installation (progress)**
- Purpose: install flow modal/screen for a single package.
- Components: package detail card (icon+name+version+description), primary "Install" button, progress bar (`warning`/`primary` fill + %), scrolling install log in `code-bg`, success text in `success`.
- Mascot: none.
- Refactor notes: install log text color should switch from default to `success` only on the final "Successfully installed" line, not the whole block.

**A10. File Creation**
- Purpose: new file modal.
- Components: centered file+icon illustration, text input (File Name), dropdown (Template), toggle (Add to .gitignore), primary "Create File" full-width button.
- Mascot: none — the "+" file icon here is not a mascot pose, keep distinct.
- Refactor notes: this is a good template for all "create new X" modals across both boards (New Chat, New Workflow, New Project) — unify into one modal component.

**A11. Console (Interactive Python)**
- Purpose: REPL-style interactive console, distinct from the raw terminal (A7).
- Components: dark console panel, `code-sm` text, toolbar (Clear/History/Run File as secondary buttons).
- Mascot: none.
- Refactor notes: near-duplicate of A7 Terminal — consider merging into one "Console" pattern with a mode toggle (Shell / Python) rather than two separate screens.

**A12. Sandbox Logs**
- Purpose: full execution/event log stream.
- Components: filter dropdown ("All Logs"), Live toggle switch, timestamped log rows (`code-sm` timestamp + `body-sm` message), "Load More" link, "Clear Logs" secondary button.
- Mascot: none.
- Refactor notes: log rows currently plain text — apply the shared trace/log row component (Section 4) with color-coded dots for log severity (info/success/warning/error) instead of uniform gray.

---

### Board B — Assistant / Dashboard Surface

**B1. Onboarding / Brand Intro**
- Purpose: first-run welcome screen ("Welcome to RIP!").
- Components: large hero mascot illustration, `headline-lg` tagline, primary "+ New Chat" button, chat/project history list below.
- Mascot: `waving.png` or `happy.png` (hero-sized) — replace the current custom illustration with the standard asset, scaled up.
- Refactor notes: decorative confetti/sparkle dots around mascot are fine sparingly, but should not appear on every screen — reserve for onboarding + celebration states only.

**B2. Server Connection**
- Purpose: connect to user's server via URL + API key.
- Components: small mascot, form inputs (Server URL, API Key with show/hide), primary "Test Connection" button, inline success confirmation (`success` text + icon), primary "Continue".
- Mascot: `waving.png` (consistent with B1) transitioning to `success.png` once connected — currently static.
- Refactor notes: this is a linear "setup wizard" pattern — reuse for any future integration connect flow instead of custom-building each one (see B7 Integrations "Connect" buttons).

**B3. Chat Interface (main)**
- Purpose: core conversational workflow — prompt, pipeline trace, findings, references.
- Components: top bar (hamburger, icon, project switcher dropdown, connection status, avatar), user bubble (solid `primary`, white text, right-aligned), assistant response (white card, left-aligned), collapsible "Pipeline Trace" row, impact/finding card (Section 4), reference file list rows, action button row (Show fixes / Related PRs / Explain — secondary pills), chat input bar with primary send button.
- Mascot: none inline — correct, avoid mascot clutter inside active conversation.
- Refactor notes: this is the most component-dense screen — enforce strict reuse: findings card = same as A6's danger styling, reference rows = same list-row component as A1's file rows.

**B4. Workspace Dashboard**
- Purpose: overview of usage, projects, activity.
- Components: greeting header with small mascot ("Good morning, Dev!"), stat cards row (Projects/Total Tokens/Cost using `stat-xl`), line chart card ("Usage Over Time"), two list cards (Top Sources, Recent Activity), suggestion cards row with arrow icon.
- Mascot: `happy.png` small, inline with greeting — keep small/secondary, not a hero moment.
- Refactor notes: chart line color must be `primary`, not a random purple shade; suggestion cards should reuse the impact-card left-accent pattern but in neutral/`primary-light` since they're not status-driven.

**B5. Agent Runs**
- Purpose: execution history + live trace detail.
- Components: back arrow + title top bar, tab bar (Executions / Live Trace), run list rows (status icon + name + timestamp + duration + status label), expandable Live Trace panel with trace/log rows and a hero rocket illustration on completion.
- Mascot: none in list; rocket illustration on trace panel is decorative, not mascot — consider replacing with `rocket.png` mascot pose for consistency, or removing if it competes with data density.
- Refactor notes: status icons (check/warning/x) must map exactly to `success`/`warning`/`danger` tokens — currently color-correct, keep it.

**B6. Workflows (Builder)** — actually 4 sub-views bundled together:
- **B6a. Workflow List**: filter tabs (All/Drafts/Published), workflow cards (icon+name+status label+version).
- **B6b. Add Block panel**: search input, categorized tool list (RIP Tools / MCP Tools / Prompt+AI) with icons.
- **B6c. Canvas/Trigger flow**: connected node diagram (Trigger → Search Code → Analyze Results → ...) with dotted connector lines.
- **B6d. Edit Block (right inspector)**: Tool dropdown, Input Bindings (`code-sm` fields), toggle options (Deep scan, Include dependencies), "Test Block" secondary + primary "Save Block".
- Mascot: none — correct, this is a dense technical builder.
- Refactor notes: this is 4 distinct component groups on one canvas — split into a clear list/canvas/inspector 3-pane layout per Section 3's master-detail pattern rather than free-floating panels.

**B6e. Run Workflow (success)**
- Purpose: completion state after running a workflow.
- Components: centered mascot hero, "All done! 🎉" headline, checklist summary (icons + text), primary "View Results" button.
- Mascot: `celebrating.png` or `party.png` (currently a sunglasses emoji-style face — replace with the actual `party.png`/`celebrating.png` asset for consistency).
- Refactor notes: this is the canonical "success hero" template — reuse structure for A9's install-success and A2's run-success states.

**B7. Integrations / Sources**
- Purpose: manage connected services (GitHub, Jira, Slack, etc).
- Components: grid of integration cards (logo + name + subtext + Connected status dot OR "Connect" secondary button).
- Mascot: none.
- Refactor notes: card grid should use the same 12px-radius/1px-border card as everywhere else — currently fine, just confirm consistent card sizing across the grid (some cards show extra metadata like "3 tools discovered").

**B8. Settings**
- Purpose: workspace-level settings navigation.
- Components: list rows (icon + label + chevron) grouped by category (Connection, Role & Defaults, Sources, Audit Log, App & Theme, Tool Details).
- Mascot: none.
- Refactor notes: merge this pattern with A8 Project Settings — they should be the identical list-row component, currently slightly different icon/spacing treatment.

**B9. Pipelines Trace (expanded)**
- Purpose: full detail view of a trace shown collapsed in B3.
- Components: vertical step list, each row = colored dot + step name + duration, indentation shows nesting.
- Mascot: none.
- Refactor notes: exact reuse target — build once as the "TraceList" component, consumed by B3 (collapsed), B5 (Live Trace), and B9 (expanded) instead of three separate implementations.

**B10. Impact Card (variants)**
- Purpose: shows the 3 severity variants (High/Medium/Low) side by side for reference.
- Components: the impact/finding card from Section 4, in 3 color states.
- Mascot: none.
- Refactor notes: this isn't a real "screen," it's a component spec sheet — keep it as documentation, not a page to refactor. Confirms: High = `danger`, Medium = `warning`, Low = `success`/neutral.

**B11. Mermaid Diagram**
- Purpose: inline auto-generated flowchart in chat (e.g. auth flow).
- Components: boxed nodes with labels, dotted directional connectors, monospace-adjacent node text.
- Mascot: none.
- Refactor notes: node fill should be `surface-container-high` (#ebe4ff) with `primary` text/border, not flat white, to visually read as "generated content" distinct from surrounding chat cards.

**B12. File References**
- Purpose: list of source files cited in a chat response.
- Components: identical list-row component to A1 file rows and B3 reference rows.
- Mascot: none.
- Refactor notes: no unique styling needed — confirm it's literally the shared FileRow component, not a bespoke one.

**B13. Follow-up Suggestions**
- Purpose: quick-action chips after an AI response.
- Components: icon + short label chip/button, secondary pill style, grid/wrap layout.
- Mascot: none.
- Refactor notes: standardize chip sizing/padding — should match the "Show fixes / Related PRs" action row from B3 exactly.

**B14. Command Palette**
- Purpose: `/`-triggered quick command modal.
- Components: modal overlay, search input, command rows (`/explain`, `/review`...) with `body-md` command + `body-sm` description, keyboard hint right-aligned.
- Mascot: none.
- Refactor notes: matches Section 4 spec already — just ensure modal overlay uses a consistent scrim opacity (~40% `text-primary`) across any other modals (A10 File Creation, A9 Install).

**B15. Project Switcher**
- Purpose: dropdown to switch active project.
- Components: dropdown list, small color dot per project (matches left-rail project dots), "+ Add Project" row at bottom.
- Mascot: none.
- Refactor notes: reuse the exact same colored-dot system as the left rail's Projects list (B1/global rail) — currently consistent, keep it that way.

**B16. Theme & Vibes**
- Purpose: accent theme picker (shown as color swatch rows).
- Components: rows of gradient swatch options.
- Mascot: none.
- Refactor notes: per Section 1 rule #2, this should be scoped to true visual customization only (e.g. chat accent) — do not let it override the core semantic/status palette or primary brand purple elsewhere in the product.

---

## 8. Suggested Refactor Order for the Agent

1. Build shared components first (Section 4) as isolated, reusable pieces.
2. Refactor Board A screens A1 → A12 (sandbox surface is more self-contained/simpler).
3. Refactor Board B screens B1 → B16 (assistant surface, more component-dense).
4. Merge duplicate patterns flagged above: A7/A11 (terminal vs console), A8/B8 (settings lists), B3/B5/B9 (trace list), A2/A9/B6e (success hero).
5. Run the Section 6 checklist against every screen as a final pass.
