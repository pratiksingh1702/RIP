"""Knowledge Lifecycle — confidence scoring, fading, archiving, evolving."""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from gateway.core.workspace.knowledge import get_workspace_knowledge

logger = logging.getLogger(__name__)

class KnowledgeLifecycle:
    """Manages the lifecycle of knowledge: active → fading → archived → forgotten."""
    
    def __init__(self):
        self.knowledge = get_workspace_knowledge()
    
    async def evolve(self, workspace_id: str) -> dict:
        """Evolve knowledge: strengthen referenced, fade unused, archive old."""
        result = {"strengthened": 0, "faded": 0, "archived": 0}
        try:
            # TODO: Implement lifecycle evolution based on reference counts and age
            pass
        except Exception as e:
            logger.error("LIFECYCLE: Evolve failed: %s", e)
        return result
    
    async def should_archive(self, knowledge_entry: dict) -> bool:
        """Check if knowledge should be archived based on age and usage."""
        created_at = knowledge_entry.get("created_at")
        if not created_at: return False
        try:
            dt = datetime.fromisoformat(created_at)
            age = datetime.utcnow() - dt
            confidence = knowledge_entry.get("confidence", 0)
            if confidence < 0.3 and age > timedelta(days=90): return True
            if age > timedelta(days=365): return True
        except Exception: pass
        return False

_lifecycle = KnowledgeLifecycle()
def get_knowledge_lifecycle() -> KnowledgeLifecycle: return _lifecycle
