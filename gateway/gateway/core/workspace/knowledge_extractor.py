"""Knowledge Extractor — extracts decisions, patterns, risks from LLM responses."""

from __future__ import annotations
import logging
from gateway.core.workspace.knowledge import get_workspace_knowledge
from gateway.core.workspace.knowledge_scoring import compute_confidence

logger = logging.getLogger(__name__)

class KnowledgeExtractor:
    """Extracts durable knowledge from AI conversations and agent executions."""
    
    def __init__(self):
        self.knowledge = get_workspace_knowledge()
    
    async def extract_from_conversation(self, workspace_id: str, query: str,
                                         response: str, llm_name: str) -> list[str]:
        """Extract potential decisions from an AI conversation."""
        ids = []
        decision_keywords = ["should", "choose", "decide", "recommend", "use", "adopt", "migrate"]
        if any(w in (query + response).lower() for w in decision_keywords):
            conf, tier = compute_confidence("llm_suggestion")
            kid = await self.knowledge.store(
                workspace_id, "decision",
                f"Potential decision from {llm_name}: {query[:100]}",
                detail=response[:500], confidence=conf,
                source_type="llm_suggestion")
            if kid: ids.append(kid)
        return ids
    
    async def extract_from_execution(self, workspace_id: str, query: str,
                                      summary: str, files_changed: list[str]) -> list[str]:
        """Extract patterns from agent executions."""
        ids = []
        if files_changed:
            for f in files_changed[:3]:
                conf, tier = compute_confidence("agent_execution")
                kid = await self.knowledge.store(
                    workspace_id, "execution",
                    f"Agent modified {f}: {summary[:100]}",
                    detail=f"Task: {query}\nResult: {summary}",
                    confidence=conf, source_type="agent_execution")
                if kid: ids.append(kid)
        return ids

_extractor = KnowledgeExtractor()
def get_knowledge_extractor() -> KnowledgeExtractor: return _extractor
