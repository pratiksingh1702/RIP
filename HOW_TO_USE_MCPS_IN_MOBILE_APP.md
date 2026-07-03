# How to Use MCPs (Model Context Protocol) in the RIP Mobile App

## Overview
The RIP (Repository Intelligence Platform) mobile app allows you to add and manage **MCP (Model Context Protocol) sources** to extend RIP's capabilities to external tools and services. MCP sources can include:
- Built-in sources: GitHub, Jira, Slack
- Custom MCP servers: Any MCP-compatible server you develop or find
- Preset sources: Linear, Notion

## Key Concepts
### Single Connection Architecture
The mobile app uses **one unified connection** to your RIP server. All MCP management is done through this single connection—no need to configure multiple separate connections!

### MCP Source Types
- **Core Sources**: Always-on sources like RIP itself (can't be deleted/disabled)
- **Built-in Sources**: GitHub, Jira, Slack (predefined but can be disabled/configured)
- **Custom MCP Servers**: Any MCP server you point to (HTTP, SSE, or stdio)

## Step-by-Step Guide

### 1. Access Sources Screen
1. Open the RIP mobile app
2. Open the **drawer menu** (top left)
3. Tap **Sources** to reach the Sources screen

### 2. Add a New Source
1. On the Sources screen, tap the **+ Add source** button
2. Choose between:
   - **Preset sources**: GitHub, Jira, Slack, Linear, Notion (tap to select, pre-fills most fields)
   - **Custom MCP**: Tap "Custom MCP" to add any MCP server
3. Fill in the fields:
   - **Name**: Descriptive name for your source
   - **Endpoint URL**: URL for the MCP server
   - **Transport**: Choose HTTP, SSE, or stdio
   - **Auth Type**: Choose Bearer token, API key, or None
   - **Credential**: If using auth, enter your token/key
   - **Domain Hints**: Tap chips to tell RIP when to use this source (e.g., "docs", "tickets")
4. Tap **Test** to verify the connection
5. If test passes, tap **Save**

### 3. Manage Existing Sources
1. On the Sources screen, tap a source row to open its detail sheet
2. From here you can:
   - Toggle enabled/disabled
   - Replace credential (never revealed)
   - Test connection
   - Delete the source (core sources like RIP can't be deleted)

### 4. Use MCP Sources in Chat
Once an MCP source is enabled and connected:
1. Open a chat in the mobile app
2. Ask a question that relates to your MCP source's domain hints
3. Watch the live pipeline trace to see when RIP uses your MCP source!
4. RIP will automatically combine results from RIP's codebase analysis and your MCP sources

## Backend Architecture
### Unified Server Endpoints
All MCP operations are handled by the Gateway, mounted at:
- `/gateway/sources` (list, create, delete sources)
- `/gateway/settings` (manage default settings)
- `/gateway/api/context` (query combined context from all enabled sources)

### Source Registry
Sources are stored in a database (SQLite for local mode, PostgreSQL for server mode) and managed by `gateway.core.sources.registry.SourceRegistry`.

### Dynamic MCP Source
Custom MCP servers are handled by `gateway.core.sources.dynamic_mcp.DynamicMCPSource` which implements the base source interface using only runtime data from the registry.

### Planner Integration
The planner uses domain hints to decide which sources to query for a given task. It always includes core sources like RIP, plus any enabled custom sources with matching domain hints.

## Troubleshooting
- **Connection failed**: Check endpoint URL, auth type, and credential are correct
- **Source not used**: Ensure domain hints match your query, or remove hints to let RIP always try it
- **Test status "unreachable"**: Verify the MCP server is running and accessible from your RIP server

## Resources
- [MCP Specification](https://modelcontextprotocol.io)
- [Gateway Documentation](gateway/docs/api.md)
