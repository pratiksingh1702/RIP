"""Knowledge Intelligence Engine — Extract, Validate, Connect, Reason, Recommend, Learn, Evolve."""

from __future__ import annotations
import logging
from gateway.core.workspace.memory import get_workspace_memory
from gateway.core.workspace.knowledge import get_workspace_knowledge
from gateway.core.workspace.knowledge_scoring import compute_confidence

logger = logging.getLogger(__name__)

class KnowledgeIntelligenceEngine:
    """Processes raw memories into durable knowledge. The brain of the workspace."""
    
    def __init__(self):
        self.memory = get_workspace_memory()
        self.knowledge = get_workspace_knowledge()
    
    async def process_event(self, workspace_id: str, event: dict) -> str | None:
        category = event.get("category", "")
        summary = event.get("summary", "")
        query = event.get("query", "")
        
        if category == "execution":
            files = event.get("files_changed", [])
            if files:
                for f in files[:3]:
                    freq = await self._count_file_changes(workspace_id, f)
                    if freq > 3:
                        conf, tier = compute_confidence("pattern_detection", frequency=freq)
                        return await self.knowledge.store(
                            workspace_id, "pattern", f"{f} changed {freq} times",
                            detail=f"File {f} has been modified {freq} times — consider refactoring",
                            confidence=conf, source_type="pattern_detection", frequency=freq)
        
        if category == "conversation" and query:
            if any(w in (query + summary).lower() for w in ["should","choose","decide","recommend","use"]):
                conf, tier = compute_confidence("llm_suggestion")
                return await self.knowledge.store(
                    workspace_id, "decision", f"Potential decision: {summary[:100]}",
                    detail=summary, confidence=conf, source_type="llm_suggestion",
                    source_event_id=event.get("id"))
        return None
    
    async def nightly_reasoning(self, workspace_id: str) -> list[dict]:
        events = await self.memory.get_events_since(workspace_id, since_hours=24)
        recommendations = []
        execs = [e for e in events if e["category"] == "execution"]
        if len(execs) > 10:
            recommendations.append({"type":"productivity","priority":"info",
                "message":f"{len(execs)} agent executions today — above average"})
        failures = [e for e in execs if e["status"] == "failed"]
        if len(failures) > 3:
            recommendations.append({"type":"risk","priority":"warning",
                "message":f"{len(failures)} failed executions — review common patterns"})
        conversations = [e for e in events if e["category"] == "conversation"]
        if len(conversations) > 20:
            recommendations.append({"type":"info","priority":"info",
                "message":f"{len(conversations)} AI conversations today — check for unextracted decisions"})
        return recommendations
    
    async def _count_file_changes(self, workspace_id: str, file_path: str) -> int:
        try:
            events = await self.memory.search(workspace_id, file_path, categories=["execution"], limit=50)
            return len([e for e in events if file_path in str(e.get("files_changed", []))])
        except Exception: return 0

_engine = KnowledgeIntelligenceEngine()
def get_knowledge_engine() -> KnowledgeIntelligenceEngine: return _engine
