"""Workspace Knowledge — extracted insights with confidence scoring."""

from __future__ import annotations
import json, logging
from uuid import uuid4
from gateway.storage.database import async_session_factory
from sqlalchemy import text

logger = logging.getLogger(__name__)

class WorkspaceKnowledge:
    """Stores extracted knowledge: decisions, patterns, relationships. Scored by confidence."""
    
    async def store(self, workspace_id: str, knowledge_type: str, summary: str,
                    detail: str | None = None, confidence: float = 0.0, source_type: str = "unknown",
                    source_event_id: str | None = None, human_override: str | None = None,
                    linked_goal_id: str | None = None, linked_entity_id: str | None = None,
                    frequency: int = 1, cross_val_count: int = 0, project_id: str | None = None) -> str:
        entry_id = str(uuid4())
        status = "active" if confidence >= 0.7 else "pending"
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    INSERT INTO workspace_knowledge (id,workspace_id,project_id,knowledge_type,summary,
                    detail,confidence,source_type,source_event_id,human_override,linked_goal_id,
                    linked_entity_id,frequency,cross_val_count,status)
                    VALUES (:id,:ws,:pid,:kt,:sum,:det,:conf,:st,:sev,:ho,:lg,:le,:fr,:cv,:stat)
                """), {"id":entry_id,"ws":workspace_id,"pid":project_id,"kt":knowledge_type,
                       "sum":summary,"det":detail,"conf":confidence,"st":source_type,
                       "sev":source_event_id,"ho":human_override,"lg":linked_goal_id,
                       "le":linked_entity_id,"fr":frequency,"cv":cross_val_count,"stat":status})
                await session.commit()
            return entry_id
        except Exception as e:
            logger.error("KNOWLEDGE: Store failed: %s", e)
            return ""

    async def search(self, workspace_id: str, query: str, knowledge_types: list[str] | None = None,
                     min_confidence: float = 0.0, limit: int = 10) -> list[dict]:
        try:
            kt_filter, params = "", {"ws":workspace_id,"q":f"%{query}%","conf":min_confidence,"lim":limit}
            if knowledge_types:
                ph = ", ".join([f":kt{i}" for i in range(len(knowledge_types))])
                kt_filter = f"AND knowledge_type IN ({ph})"
                for i,k in enumerate(knowledge_types): params[f"kt{i}"] = k
            async with async_session_factory() as session:
                r = await session.execute(text(f"""
                    SELECT id,knowledge_type,summary,detail,confidence,source_type,human_override,
                           linked_goal_id,linked_entity_id,frequency,cross_val_count,status,created_at
                    FROM workspace_knowledge WHERE workspace_id=:ws {kt_filter}
                    AND confidence>=:conf AND (summary LIKE :q OR detail LIKE :q)
                    ORDER BY confidence DESC, created_at DESC LIMIT :lim
                """), params)
                return [{"id":row[0],"knowledge_type":row[1],"summary":row[2],"detail":row[3],
                         "confidence":row[4],"source_type":row[5],"human_override":row[6],
                         "linked_goal_id":row[7],"linked_entity_id":row[8],"frequency":row[9],
                         "cross_val_count":row[10],"status":row[11],
                         "created_at":row[12].isoformat() if row[12] else None} for row in r.fetchall()]
        except Exception as e:
            logger.error("KNOWLEDGE: Search failed: %s", e)
            return []

    async def approve(self, knowledge_id: str) -> bool:
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    UPDATE workspace_knowledge SET confidence=0.98, human_override='approved',
                    status='active', updated_at=CURRENT_TIMESTAMP WHERE id=:id
                """), {"id":knowledge_id})
                await session.commit()
            return True
        except Exception as e:
            logger.error("KNOWLEDGE: Approve failed: %s", e)
            return False

    async def reject(self, knowledge_id: str) -> bool:
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    UPDATE workspace_knowledge SET confidence=0.0, human_override='rejected',
                    status='archived', updated_at=CURRENT_TIMESTAMP WHERE id=:id
                """), {"id":knowledge_id})
                await session.commit()
            return True
        except Exception as e:
            logger.error("KNOWLEDGE: Reject failed: %s", e)
            return False

    async def get_pending_review(self, workspace_id: str, limit: int = 10) -> list[dict]:
        try:
            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT id,knowledge_type,summary,detail,confidence,source_type,created_at
                    FROM workspace_knowledge WHERE workspace_id=:ws AND status='pending'
                    ORDER BY confidence DESC, created_at DESC LIMIT :lim
                """), {"ws":workspace_id,"lim":limit})
                return [{"id":row[0],"knowledge_type":row[1],"summary":row[2],"detail":row[3],
                         "confidence":row[4],"source_type":row[5],
                         "created_at":row[6].isoformat() if row[6] else None} for row in r.fetchall()]
        except Exception as e:
            logger.error("KNOWLEDGE: Get pending failed: %s", e)
            return []

    async def get_by_goal(self, workspace_id: str, goal_id: str) -> list[dict]:
        try:
            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT id,knowledge_type,summary,confidence,status,created_at
                    FROM workspace_knowledge WHERE workspace_id=:ws AND linked_goal_id=:gid
                    ORDER BY created_at DESC
                """), {"ws":workspace_id,"gid":goal_id})
                return [{"id":row[0],"knowledge_type":row[1],"summary":row[2],"confidence":row[3],
                         "status":row[4],"created_at":row[5].isoformat() if row[5] else None}
                        for row in r.fetchall()]
        except Exception as e:
            logger.error("KNOWLEDGE: Get by goal failed: %s", e)
            return []

    async def update_frequency(self, knowledge_id: str) -> bool:
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    UPDATE workspace_knowledge SET frequency = frequency + 1,
                    updated_at=CURRENT_TIMESTAMP WHERE id=:id
                """), {"id":knowledge_id})
                await session.commit()
            return True
        except Exception: return False

    async def get_suggestions(self, workspace_id: str, project_id: str | None = None) -> list[dict]:
        """Generate suggestions from workspace patterns."""
        suggestions = []
        try:
            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT files_changed, COUNT(*) as cnt FROM workspace_memory
                    WHERE workspace_id=:ws AND category='execution' AND files_changed IS NOT NULL
                    GROUP BY files_changed HAVING cnt > 3 ORDER BY cnt DESC LIMIT 5
                """), {"ws": workspace_id})
                for row in r.fetchall():
                    files = json.loads(row[0]) if row[0] else []
                    if files:
                        suggestions.append({"type":"frequent_changes","message":f"{files[0]} changed {row[1]} times","files":files[:3],"count":row[1]})
                r = await session.execute(text("""
                    SELECT query, summary, COUNT(*) as cnt FROM workspace_memory
                    WHERE workspace_id=:ws AND status='failed' GROUP BY query HAVING cnt > 1 ORDER BY cnt DESC LIMIT 3
                """), {"ws": workspace_id})
                for row in r.fetchall():
                    suggestions.append({"type":"recurring_failure","message":f"'{row[0][:80]}' failed {row[2]} times","query":row[0],"summary":row[1]})
        except Exception as e:
            logger.error("KNOWLEDGE: Suggestions failed: %s", e)
        return suggestions

_knowledge = WorkspaceKnowledge()
def get_workspace_knowledge() -> WorkspaceKnowledge: return _knowledge
