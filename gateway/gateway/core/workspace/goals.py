"""Goal Engine — goals, features, tasks, progress tracking."""

from __future__ import annotations
import json, logging
from uuid import uuid4
from gateway.storage.database import async_session_factory
from sqlalchemy import text

logger = logging.getLogger(__name__)

class GoalEngine:
    """Manages workspace goals: create, track progress, link to knowledge."""
    
    async def create(self, workspace_id: str, name: str, description: str = "",
                     priority: str = "medium", deadline: str | None = None,
                     parent_goal_id: str | None = None, created_by: str | None = None) -> str:
        goal_id = str(uuid4())
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    INSERT INTO workspace_goals (id,workspace_id,name,description,priority,deadline,
                    parent_goal_id,created_by) VALUES (:id,:ws,:n,:d,:p,:dl,:pid,:by)
                """), {"id":goal_id,"ws":workspace_id,"n":name,"d":description,"p":priority,
                       "dl":deadline,"pid":parent_goal_id,"by":created_by})
                await session.commit()
            return goal_id
        except Exception as e:
            logger.error("GOALS: Create failed: %s", e)
            return ""

    async def update_progress(self, goal_id: str, progress: float) -> bool:
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    UPDATE workspace_goals SET progress=:p,
                    status=CASE WHEN :p>=100 THEN 'completed' ELSE status END,
                    updated_at=CURRENT_TIMESTAMP WHERE id=:id
                """), {"p":min(progress,100),"id":goal_id})
                await session.commit()
            return True
        except Exception as e:
            logger.error("GOALS: Update progress failed: %s", e)
            return False

    async def get_active(self, workspace_id: str, limit: int = 10) -> list[dict]:
        try:
            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT id,name,description,status,progress,priority,deadline,created_at
                    FROM workspace_goals WHERE workspace_id=:ws AND status IN ('active','in_progress')
                    ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC
                    LIMIT :lim
                """), {"ws":workspace_id,"lim":limit})
                return [{"id":row[0],"name":row[1],"description":row[2],"status":row[3],
                         "progress":row[4],"priority":row[5],"deadline":row[6],
                         "created_at":row[7].isoformat() if row[7] else None} for row in r.fetchall()]
        except Exception as e:
            logger.error("GOALS: Get active failed: %s", e)
            return []

    async def get_all(self, workspace_id: str) -> list[dict]:
        try:
            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT id,name,description,status,progress,priority,deadline,created_at
                    FROM workspace_goals WHERE workspace_id=:ws ORDER BY created_at DESC
                """), {"ws":workspace_id})
                return [{"id":row[0],"name":row[1],"description":row[2],"status":row[3],
                         "progress":row[4],"priority":row[5],"deadline":row[6],
                         "created_at":row[7].isoformat() if row[7] else None} for row in r.fetchall()]
        except Exception as e:
            logger.error("GOALS: Get all failed: %s", e)
            return []

_goals = GoalEngine()
def get_goal_engine() -> GoalEngine: return _goals
