# MCP Connection Guide

## Configuring MCP Agents to Use Context Gateway

Context Gateway provides an MCP server that AI coding agents like Claude Code, Cursor, Codex, etc.

### 1. Get MCP Config
```bash
uv run gateway mcp config
```
This prints out the MCP server JSON configuration you can add to your agent's settings!

### 2. Claude Code
Edit your Claude Code config file (`.claude/claude_desktop_config.json usually):
Add to `"mcpServers": {
  "context-gateway": {
    "command": "uv",
    "args": ["run", "gateway", "start", "--mcp"],
    "cwd": "/path/to/rip/gateway"
  }
}

### 3. Cursor
In Cursor, go to Settings → MCP → Add MCP Server and paste the configuration from `gateway mcp config!

### 4. Codex
Same as above, add to Codex's MCP config

## Available MCP Tools
1. `get_context`: Get relevant context from all sources
2. `search_codebase`: Search codebase
3. `explain_architecture`: Explain architecture
4. `validate_change`: Validate a code change

