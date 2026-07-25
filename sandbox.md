# Sandbox = Your Allocated Computer

## The Mental Model Shift

Stop thinking of it as a "sandbox." Think of it as **your cloud computer**. 

When you get a new MacBook, you don't reinstall Python for every terminal window. You install it once, and every terminal sees it. Same with the sandbox.

---

## How It Should Work

### One Sandbox = One Computer

```
┌─────────────────────────────────────────────────────────────┐
│  YOUR ALLOCATED COMPUTER: flutter_music_app                 │
│                                                             │
│  System-wide (installed once, available everywhere):        │
│  ├── Python 3.12                                            │
│  ├── Node.js 20                                             │
│  ├── Flutter SDK 3.x                                        │
│  ├── ripgrep, bat, fd, htop, git, curl                      │
│  └── Claude Code (npm install -g, available everywhere)     │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  TERMINAL 1      │  │  TERMINAL 2      │                │
│  │  $ flutter run   │  │  $ claude        │                │
│  │  $ dart analyze  │  │  > fix auth bug  │                │
│  │  $ git push      │  │                  │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  TERMINAL 3      │  │  TERMINAL 4      │                │
│  │  $ npm test      │  │  $ htop          │                │
│  │  $ pytest        │  │  $ tail -f logs  │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                             │
│  All terminals share:                                       │
│  • Same filesystem (/workspace)                             │
│  • Same installed tools (global npm/pip/cargo)              │
│  • Same environment variables                               │
│  • Same running processes                                   │
│  • Same git config                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Multiple Terminal Windows

In the mobile app, you don't get ONE terminal. You get a **terminal manager**:

```
┌──────────────────────────────────────────────┐
│  🖥️ flutter_music_app                        │
│  ┌──────────────────────────────────────────┐│
│  │ [Term 1: flutter run] [Term 2: claude]  ││  ← Tabs!
│  │ [Term 3: logs]        [+ New Terminal]  ││
│  └──────────────────────────────────────────┘│
│                                              │
│  ┌──────────────────────────────────────────┐│
│  │ TERMINAL 2: claude                       ││
│  │                                          ││
│  │ $ claude                                 ││
│  │ > fix the auth token refresh bug         ││
│  │                                          ││
│  │ Claude: I'll look at auth.py...          ││
│  │ Claude: Found the issue on line 47       ││
│  │ Claude: The token check uses `>`         ││
│  │         instead of `>=`                  ││
│  │                                          ││
│  │ [Approve] [Reject]                       ││
│  └──────────────────────────────────────────┘│
│                                              │
│  ┌──────────────────────────────────────────┐│
│  │ $ _                                      ││  ← Input bar
│  └──────────────────────────────────────────┘│
└──────────────────────────────────────────────┘
```

---

## How It Works Technically

### One Container, Many PTY Sessions

```python
# gateway/core/sandbox/terminal.py

class TerminalManager:
    """Manages multiple terminal sessions for one sandbox."""
    
    def __init__(self, sandbox_id: str):
        self.sandbox_id = sandbox_id
        self.terminals: dict[str, TerminalSession] = {}
    
    async def create_terminal(self, name: str = "term-1") -> TerminalSession:
        """Open a new terminal window in the sandbox."""
        exec_id, socket = get_orchestrator().exec_interactive(
            sandbox_id=self.sandbox_id,
            command="/bin/bash",  # Same shell for all terminals
            workdir="/workspace"
        )
        session = TerminalSession(
            terminal_id=str(uuid4()),
            sandbox_id=self.sandbox_id,
            name=name,
            exec_id=exec_id,
            socket=socket
        )
        self.terminals[session.terminal_id] = session
        return session
```

### All Terminals Share Everything

```
DOCKER CONTAINER: sandbox-flutter-music-app
│
├── /workspace/              ← Shared filesystem
│   ├── lib/
│   ├── pubspec.yaml
│   └── test/
│
├── /usr/local/bin/          ← Shared installed tools
│   ├── python3
│   ├── node
│   ├── flutter
│   ├── claude        ← Installed once, all terminals see it
│   └── ripgrep
│
├── /root/.gitconfig         ← Shared git identity
├── /root/.claude.json       ← Shared AI config
│
├── PTY 1: /bin/bash         ← Terminal 1 (flutter run)
├── PTY 2: /bin/bash         ← Terminal 2 (claude)
├── PTY 3: /bin/bash         ← Terminal 3 (htop)
└── PTY 4: /bin/bash         ← Terminal 4 (npm test)
```

Because they're all `docker exec` sessions into the **same container**, they share:
- Filesystem (install once, available everywhere)
- Processes (can see each other's running processes)
- Environment variables
- Network (same localhost)

---

## Mobile UI — Terminal Tabs

```dart
class SandboxScreen extends ConsumerStatefulWidget {
  // ...
}

class _SandboxScreenState extends ConsumerState<SandboxScreen> {
  int _activeTerminalIndex = 0;
  
  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sandboxProvider);
    final terminals = state.terminals;
    
    return Scaffold(
      body: Column(
        children: [
          // Terminal tabs
          SizedBox(
            height: 40,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                for (var i = 0; i < terminals.length; i++)
                  GestureDetector(
                    onTap: () => setState(() => _activeTerminalIndex = i),
                    child: Container(
                      padding: EdgeInsets.symmetric(horizontal: 16),
                      decoration: BoxDecoration(
                        color: i == _activeTerminalIndex 
                            ? Colors.white10 
                            : Colors.transparent,
                        border: Border(
                          bottom: BorderSide(
                            color: i == _activeTerminalIndex 
                                ? AppColors.primary 
                                : Colors.transparent,
                            width: 2,
                          ),
                        ),
                      ),
                      child: Row(
                        children: [
                          Text(terminals[i].name),
                          SizedBox(width: 8),
                          GestureDetector(
                            onTap: () => _closeTerminal(i),
                            child: Icon(Icons.close, size: 14),
                          ),
                        ],
                      ),
                    ),
                  ),
                // Add terminal button
                IconButton(
                  icon: Icon(Icons.add),
                  onPressed: () => _createTerminal(),
                ),
              ],
            ),
          ),
          
          // Active terminal
          Expanded(
            child: TerminalView(
              session: terminals[_activeTerminalIndex],
            ),
          ),
        ],
      ),
    );
  }
}
```

---

## User Experience

### Installing a Tool — Once

```
Terminal 1:
  $ npm install -g @anthropic-ai/claude-code
  Installed successfully!

Terminal 2 (new tab):
  $ claude --version
  Claude Code v1.2.3    ← Available immediately!
```

### Running Multiple Things

```
Tab 1: $ flutter run          ← App running
Tab 2: $ claude               ← AI assistant
Tab 3: $ tail -f logs/app.log ← Watching logs
Tab 4: $ htop                 ← Monitoring resources
```

### Switching Context

Just swipe between tabs. Like a browser. Like VS Code's terminal panel. Like iTerm2.

---

## What This Enables

| Workflow | How |
|----------|-----|
| Run tests in one tab, AI in another | `npm test` in Tab 1, `claude` in Tab 2 |
| Watch logs while coding | `tail -f` in Tab 3, editing in Tab 1 |
| Long-running dev server | `flutter run` in one tab, keeps running |
| Install tools once | `npm install -g` in any tab, available everywhere |
| Multi-task from phone | Switch between tabs, just like desktop |

---

## Implementation

| What | How | Effort |
|------|-----|--------|
| Multiple PTY sessions | `docker exec` multiple bash processes in same container | 0.5 day |
| Terminal tabs UI | Flutter TabBar + multiple TerminalView widgets | 1 day |
| Session manager | Track active terminals per sandbox | 0.5 day |
| WebSocket per terminal | Each terminal gets its own WS connection | 0.5 day |
| Tool installation | Any terminal can `apt/pip/npm install` — shared filesystem | Already works |
| **Total** | | **~2.5 days** |

The sandbox is just a Linux computer. You get as many terminal windows as you want. Install something once, use it everywhere. Like a real machine.