Currently no — the sandbox terminal sends one command and waits for output. It's not an interactive TTY session. Codex asked "Do you trust this directory? › 1. Yes, 2. No" but the user can't respond.

## How to Make Interactive Commands Work

### The Problem
Each command from mobile runs as a new `bash -c "command"` process. There's no persistent shell session. Codex/Aider ask questions, but nobody's listening.

### The Solution: Persistent PTY Session

Instead of one-off `bash -c`, create a **persistent bash process** when the terminal opens, and pipe all input/output through it:

```
Mobile Terminal opens
  ↓
Server creates: bash (persistent, running as a PTY)
  ↓
User types: codex exec "fix bug"
  ↓
Server writes to bash's stdin
  ↓
Bash runs codex
  ↓
Codex asks: "Do you trust this directory? [y/N]"
  ↓
Output streams to mobile → user sees the question
  ↓
User types: y
  ↓
Server writes "y\n" to bash's stdin
  ↓
Codex continues
```

### What Already Exists
The stream agent (`stream_agent.py`) already uses `pty.fork()` — it creates a real PTY! The issue is the terminal creates a **new connection per command** instead of keeping one open.

### Changes Needed

**Backend (`terminal.py`):**

Instead of opening a new TCP connection for each command, keep ONE connection open:

```python
class TerminalSession:
    def __init__(self):
        self._persistent_reader = None  # Keep one TCP connection
        self._persistent_writer = None
    
    async def _run_command(self, command, sanitized):
        if self._persistent_writer is None:
            # First command — open persistent connection
            port = await self._get_stream_port()
            self._persistent_reader, self._persistent_writer = \
                await asyncio.open_connection("127.0.0.1", port)
        
        # Send command through existing connection
        request = json.dumps({"command": command, "workdir": "/workspace"}) + "\n"
        self._persistent_writer.write(request.encode())
        await self._persistent_writer.drain()
        
        # Read streaming output until END_MARKER
        ...
```

**Stream Agent (`stream_agent.py`):**

Already supports multiple commands on one connection (the TCP server stays alive). Just need to handle stdin forwarding for interactive commands:

```python
async def handle_client(reader, writer):
    while True:  # Keep connection alive for multiple commands
        line = await reader.readline()
        if not line:
            break
        req = json.loads(line.decode())
        command = req.get("command", "")
        await run_command_pty(command, "/workspace", writer)
```

**Frontend (`terminal_view.dart`):**

When output contains interactive prompts (detected by patterns like `[y/N]`, `›`, `?`), show input field:

```dart
// Detect interactive prompt
bool isInteractivePrompt(String output) {
  return RegExp(r'\[y/N\]|\[Y/n\]|›|\? $|\(yes/no\)').hasMatch(output);
}

// When prompt detected, show quick response buttons
if (isInteractivePrompt(lastOutput)) {
  return Column(children: [
    TerminalOutput(output: lastOutput),
    Row(children: [
      QuickResponseButton(label: "Yes", onTap: () => sendCommand("y")),
      QuickResponseButton(label: "No", onTap: () => sendCommand("n")),
      QuickResponseButton(label: "Continue", onTap: () => sendCommand("")),
    ]),
  ]);
}
```

---

## What This Enables

| Tool | Before | After |
|------|--------|-------|
| Codex | Asks "Trust directory?" → stuck | User taps "Yes" → continues |
| Aider | Asks "Apply edit? [y/N]" → stuck | User taps "Yes" → edit applied |
| npm init | Asks "package name:" → stuck | User types name → continues |
| git commit | Opens editor → stuck | User types message → commits |
| pip install | "Proceed? [y/N]" → stuck | User taps "Yes" → installs |

---

## Implementation Priority

| Step | Effort | Impact |
|------|--------|--------|
| 1. Persistent TCP connection in terminal.py | 2 hours | Foundation |
| 2. Interactive prompt detection in Flutter | 1 hour | User sees questions |
| 3. Quick response buttons (Yes/No/Continue) | 1 hour | One-tap answers |
| 4. Free-text input for prompts | 0.5 hour | For "package name:" etc |
| 5. Handle multi-turn conversations | 1 hour | Full interactive apps |

**Total: ~1.5 days for full interactive terminal support**# ANSI/String Handling — Complete Fix Plan

## The Problem

The terminal is drowning in raw ANSI escape codes. Users see garbage:

```
[?2004h[>4;0m[>7u[?1004h[6n]10;?\]11;?\
[?2026h[1;1H[J[1;55H[0m[49m[K
[2;2H[0m[49m[K
```

Instead of:
```
Welcome to Codex, OpenAI's command-line coding agent
> You are in /workspace
  Do you trust the contents of this directory?
› 1. Yes, continue
  2. No, quit
```

This affects: Codex TUI, Aider spinner, progress bars, colored output, cursor positioning.

---

## What Needs to Change (Both Sides)

### Backend: Strip or Convert ANSI Before Sending

In `terminal.py`, after reading output from the stream agent, process it:

```python
import re

# ANSI stripping patterns
ANSI_ESCAPE = re.compile(r'''
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or [ for CSI sequences
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
''', re.VERBOSE)

# OSC sequences (operating system commands)
OSC_ESCAPE = re.compile(r'\x1B\].*?(?:\x07|\x1B\\)')

# DCS sequences (device control strings)
DCS_ESCAPE = re.compile(r'\x1BP.*?\x1B\\')

# APC, PM, SOS sequences
OTHER_ESCAPE = re.compile(r'\x1B[PX^_].*?\x1B\\')

def clean_ansi(text: str) -> str:
    """Remove all ANSI escape sequences, keeping only readable text."""
    text = OSC_ESCAPE.sub('', text)
    text = DCS_ESCAPE.sub('', text)
    text = OTHER_ESCAPE.sub('', text)
    text = ANSI_ESCAPE.sub('', text)
    # Remove cursor positioning leftovers (empty lines from clear screen)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
```

But **better than stripping**: convert common ANSI to Flutter-understandable markers:

```python
def ansi_to_markers(text: str) -> str:
    """Convert common ANSI to simple markers the Flutter UI can render."""
    # Bold
    text = re.sub(r'\x1B\[1m(.*?)\x1B\[0m', r'**\1**', text)
    text = re.sub(r'\x1B\[1m(.*?)\x1B\[22m', r'**\1**', text)
    # Colors → ignore (Flutter handles its own colors)
    text = re.sub(r'\x1B\[[\d;]+m', '', text)
    # Cursor positioning → collapse to newlines
    text = re.sub(r'\x1B\[\d+;\d+H', '\n', text)
    # Clear screen → separator
    text = re.sub(r'\x1B\[2J', '\n───\n', text)
    # Clear line
    text = re.sub(r'\x1B\[K', '', text)
    # Progress bar characters → keep
    text = re.sub(r'\x1B\[\?25[hl]', '', text)  # Hide/show cursor
    text = re.sub(r'\x1B\[\?20\d\dh', '', text)  # Other modes
    return text
```

---

### Frontend: Render ANSI-Aware Terminal

The Flutter `_TerminalLine` widget currently strips some ANSI but misses most. Replace with a proper ANSI parser:

```dart
// In terminal_view.dart, replace _stripAnsi with:

String _processAnsiOutput(String text) {
  // ANSI escape sequence pattern
  final ansiPattern = RegExp(
    '\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\].*?(?:\x07|\x1B\\))'
  );
  
  // Remove cursor control sequences
  String cleaned = text
    .replaceAll(RegExp(r'\x1B\[\?25[hl]'), '')  // cursor show/hide
    .replaceAll(RegExp(r'\x1B\[\d+;\d+H'), '\n') // cursor position
    .replaceAll(RegExp(r'\x1B\[[JK]'), '')        // erase display/line
    .replaceAll(RegExp(r'\x1B\[\d+[ABCD]'), '');   // cursor movement
  
  // Convert color codes to nothing (we use our own colors)
  cleaned = cleaned.replaceAll(RegExp(r'\x1B\[\d+(;\d+)*m'), '');
  
  // Strip remaining escape sequences
  cleaned = cleaned.replaceAll(ansiPattern, '');
  
  // Clean up multiple blank lines
  cleaned = cleaned.replaceAll(RegExp(r'\n{3,}'), '\n\n');
  
  return cleaned.trim();
}
```

But the **best approach** is a dedicated terminal renderer package. Add to `pubspec.yaml`:

```yaml
dependencies:
  flutter_terminal: ^1.0.0  # or xterm_flutter
```

These packages handle:
- ANSI color codes → actual Flutter colors
- Cursor positioning → proper layout
- Bold/italic/underline → Flutter text styles
- Progress bars → animated widgets
- Box drawing characters → proper lines
- Mouse events (for TUI apps)

---

### What The User Sees — Before vs After

**Before (raw ANSI):**
```
[?2004h[>4;0m[1;1H[J[1;55H[0m[49m[KWelcome[1;11Hto[1;14H[1mCodex[22m
```

**After (clean):**
```
Welcome to Codex
```

**After (rich):**
```
┌──────────────────────────────────────────┐
│ Welcome to Codex                         │
│ OpenAI's command-line coding agent       │
│                                          │
│ > You are in /workspace                  │
│   Do you trust this directory?           │
│                                          │
│ ● Yes, continue                          │
│ ○ No, quit                               │
└──────────────────────────────────────────┘
```

---

## Implementation Priority

| Step | Where | What | Effort |
|------|-------|------|--------|
| 1 | `terminal.py` | Add ANSI stripping before broadcast | 30 min |
| 2 | `terminal_view.dart` | Improve `_stripAnsi` with full pattern | 1 hour |
| 3 | `pubspec.yaml` | Add `flutter_terminal` package | 10 min |
| 4 | `terminal_view.dart` | Replace custom view with proper terminal widget | 3 hours |
| 5 | `terminal.py` | Add ANSI-to-marker conversion for bold/colors | 1 hour |

**Total: ~1 day for production-quality ANSI handling**

The `flutter_terminal` package gives you xterm.js-level terminal rendering in Flutter — handles everything Codex, Aider, pip, npm, and any CLI tool throws at it. Users see what they'd see in a real terminal, not raw escape codes.# Terminal UX Enhancement — From User's Perspective

## Current Experience (What You Have)

The terminal works. Commands execute. Streaming works. But the experience is **raw** — it feels like SSH'ing into a server, not like using a polished product.

---

## The Problems Users Feel

### 1. "I don't know what's installed"
User types `codex --version` → "command not found". They don't know codex IS installed, just at a weird path.

**Fix: Smart PATH + Tool Discovery**
- Sandbox auto-scans common install locations and adds them to PATH
- On sandbox creation, show a welcome card: "✅ Python 3.12 | ✅ Node 20 | ✅ Codex CLI | ✅ Aider | ✅ curl"
- Type `?` or `help` to see available tools

### 2. "Every command needs the full path"
`/usr/local/lib/python3.12/site-packages/codex_cli_bin/bin/codex` is unusable.

**Fix: Auto-aliases + Profile Persistence**
- Sandbox profile stores PATH additions and aliases
- On creation, inject: `alias codex="/usr/local/.../bin/codex"`, `alias aider="aider"`
- User types `codex` — works immediately

### 3. "I type a command, wait, see output. Like a telegram from 1990."
No progress indication for long commands. `pip install` sits silent for 30 seconds.

**Fix: Rich Progress Indicators**
- Spinner for "Working..." commands
- Progress bars for downloads (pip already outputs them — show them)
- Estimated time remaining for long operations
- "Command completed in 12.3s ✓" footer

### 4. "I can't see what happened 5 commands ago"
Output scrolls away. No history search.

**Fix: Command History with Search**
- Swipe up on terminal → command history
- Search: "pip" → shows all pip commands
- Tap to re-run
- Bookmark important outputs

### 5. "I installed Flask. Next sandbox, it's gone."
Every new sandbox is empty. User reinstalls everything.

**Fix: Persistent Profiles**
- "Save as Profile" button in sandbox header
- Next sandbox: "Load Profile: My Python Setup" → everything pre-installed
- Profile stores: apt packages, pip packages, npm packages, env vars, aliases, dotfiles

### 6. "I don't know what the AI tools can do"
User has Codex, Aider, Ollama — but doesn't know which to use for what.

**Fix: Tool Suggestions Based on Intent**
- Type "fix bug" → suggests: `aider --model ollama_chat/qwen2.5:3b`
- Type "create app" → suggests: `codex exec --oss ...`
- Type "explain code" → suggests: `codex exec "explain this code"`
- Quick-action chips above terminal: [🐛 Fix Bug] [📝 Edit File] [🔍 Explain] [🚀 Deploy]

### 7. "The terminal looks like a black hole"
No visual structure. Just text on dark background.

**Fix: Visual Structure**
- Each command output is a **card** with subtle border
- Command header shows: `$ command` with timestamp and duration
- Error output has red left-border
- Success output has green left-border
- Streaming output has animated left-border
- Different background shade for command blocks vs output

### 8. "I accidentally closed the terminal. Everything is gone."
Sandbox session ends = all work lost.

**Fix: Session Persistence**
- Auto-snapshot on terminal close
- "Resume Session" on next open
- Show: "You have a saved session from 10 minutes ago. Resume?"
- Running processes survive (if sandbox isn't stopped)

### 9. "I can't multi-task"
One terminal, one command at a time. Can't run server AND edit files.

**Fix: Terminal Tabs**
- Multiple tabs in the same sandbox (already designed)
- Tab 1: `python app.py` (server running)
- Tab 2: `codex exec "fix the login bug"`
- Tab 3: `tail -f logs/access.log`
- Swipe between tabs

### 10. "I type the same long commands repeatedly"
`/usr/local/lib/python3.12/site-packages/codex_cli_bin/bin/codex exec --oss --local-provider ollama --model qwen2.5:3b --skip-git-repo-check --sandbox workspace-write`

**Fix: Snippets + Quick Commands**
- Save command as snippet: "codex-fix"
- Quick command bar: configurable buttons
- Tap "Codex Fix" → inserts the full command, ready to add the prompt

### 11. "I paste something and it breaks"
Multi-line paste becomes one mangled line. Heredocs fail.

**Fix: Paste Detection + Smart Handling**
- Detect multi-line paste → show "Paste as multi-line? [Yes] [As Single Line]"
- Or auto-detect heredoc syntax and handle correctly
- "Paste file content" button → writes to temp file, shows path

### 12. "I want to edit a file visually, not with nano"
Terminal editors are painful on mobile.

**Fix: Quick File Editor**
- Tap file path in output → opens simple editor overlay
- Syntax highlighting for code files
- Save → writes back to sandbox
- "Edit with AI" button → sends to Codex/Aider

---

## The Ideal Terminal Experience

```
┌──────────────────────────────────────────────────────────┐
│ 🖥️ Python 3.12 | 📦 flask, codex, aider | 🔵 Online    │
│ [Tab1: Server] [Tab2: Codex] [Tab3: Logs] [+]            │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─ QUICK ACTIONS ──────────────────────────────────┐   │
│  │ [🐛 Fix Bug] [📝 Edit File] [🔍 Explain] [🚀 Run]│   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ $ pip install flask ────── 12.3s ✓ ─────────────┐  │
│  │ ████████████████████████████ 100%                  │  │
│  │ Successfully installed flask-3.1.3                 │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ $ python app.py ────── running... ───────────────┐  │
│  │ * Serving Flask app 'app'                          │  │
│  │ * Running on http://0.0.0.0:5000                   │  │
│  │ [Stop] [Open in Browser]                           │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ $ codex exec "fix the login" ───────────────────┐  │
│  │ ░░░░ Thinking...                                   │  │
│  │ Found bug in auth.py line 47                       │  │
│  │ Fixed. Tests pass. ✓                               │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ $ _                                            [📋] [⏎]│
│ [codex-fix] [pip-install] [pytest] [git-push]           │
└──────────────────────────────────────────────────────────┘
```

---

## Priority Implementation

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| 🔴 P0 | Command cards with visual structure | 1 day | Huge — makes terminal readable |
| 🔴 P0 | Tool discovery on sandbox start | 0.5 day | Eliminates "what's installed?" |
| 🔴 P0 | Progress indicators for long commands | 0.5 day | Eliminates "is it working?" |
| 🟡 P1 | Quick-action chips based on intent | 1 day | Guides users to right tool |
| 🟡 P1 | Command history with search | 1 day | Saves typing |
| 🟡 P1 | Persistent profiles | 2 days | No reinstall every sandbox |
| 🟢 P2 | Terminal tabs | 1 day | Multi-tasking |
| 🟢 P2 | File editor overlay | 1.5 days | Visual editing on mobile |
| 🟢 P2 | Snippets + quick commands | 0.5 day | Saves repetitive typing |
| 🟢 P3 | Paste detection | 0.5 day | Quality of life |
| 🟢 P3 | Session persistence | 1 day | Resume after close |

**Total to production-ready terminal UX: ~10 days**