"""MCP Server — exposes workspace context, knowledge, goals, entities as MCP tools."""

from __future__ import annotations
import json
from gateway.core.workspace.memory import get_workspace_memory
from gateway.core.workspace.knowledge import get_workspace_knowledge
from gateway.core.workspace.goals import get_goal_engine
from gateway.core.workspace.entities import get_entity_graph
from gateway.core.workspace.context_injector import get_context_injector

class ContextMCPServer:
    """MCP server exposing Context Gateway as tools for Claude, Codex, Cursor."""
    
    def __init__(self):
        self.memory = get_workspace_memory()
        self.knowledge = get_workspace_knowledge()
        self.goals = get_goal_engine()
        self.entities = get_entity_graph()
        self.injector = get_context_injector()
    
    def get_tools(self) -> list[dict]:
        return [
            {"name":"get_workspace_context","description":"ALWAYS call this before answering any question about this codebase. Returns current project, recent decisions, active files, and open tasks.",
             "inputSchema":{"type":"object","properties":{"workspace_id":{"type":"string"}},"required":["workspace_id"]}},
            {"name":"search_knowledge","description":"Search workspace knowledge for past decisions, patterns, and context.",
             "inputSchema":{"type":"object","properties":{"workspace_id":{"type":"string"},"query":{"type":"string"},"min_confidence":{"type":"number","default":0.5}},"required":["workspace_id","query"]}},
            {"name":"get_active_goals","description":"Get current active goals and their progress for this workspace.",
             "inputSchema":{"type":"object","properties":{"workspace_id":{"type":"string"}},"required":["workspace_id"]}},
            {"name":"get_related_entities","description":"Get all entities related to a given entity (goal, decision, PR, person).",
             "inputSchema":{"type":"object","properties":{"workspace_id":{"type":"string"},"entity_id":{"type":"string"}},"required":["workspace_id","entity_id"]}},
        ]
    
    async def handle_tool_call(self, tool_name: str, arguments: dict) -> str:
        ws = arguments.get("workspace_id", "default")
        if tool_name == "get_workspace_context":
            return json.dumps({"context": await self.injector.build_context_header(ws)})
        elif tool_name == "search_knowledge":
            return json.dumps({"results": await self.knowledge.search(ws, arguments["query"], min_confidence=arguments.get("min_confidence", 0.5))})
        elif tool_name == "get_active_goals":
            return json.dumps({"goals": await self.goals.get_active(ws)})
        elif tool_name == "get_related_entities":
            return json.dumps({"entities": await self.entities.get_related(ws, arguments["entity_id"])})
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

_mcp_server = ContextMCPServer()
def get_mcp_server() -> ContextMCPServer: return _mcp_server
