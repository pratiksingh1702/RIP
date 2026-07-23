"""Workspace Memory — raw events storage. Append-only, immutable. Knowledge is extracted from these."""

from __future__ import annotations
import json, logging
from uuid import uuid4
from gateway.storage.database import async_session_factory
from sqlalchemy import text

logger = logging.getLogger(__name__)

class WorkspaceMemory:
    """Stores raw events. Never modified. The source of truth for everything that happened."""
    
    async def record(self, workspace_id: str, category: str, query: str | None = None,
                     summary: str | None = None, result_data: dict | None = None,
                     project_id: str | None = None, intent: str | None = None,
                     sources_used: list | None = None, context_assembled: str | None = None,
                     files_changed: list | None = None, tokens_used: int = 0,
                     tokens_budgeted: int = 0, duration_seconds: float = 0,
                     status: str = "completed", created_by: str | None = None) -> str:
        entry_id = str(uuid4())
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    INSERT INTO workspace_memory (id,workspace_id,project_id,category,intent,query,summary,
                    result_data,sources_used,context_assembled,files_changed,tokens_used,tokens_budgeted,
                    duration_seconds,status,created_by)
                    VALUES (:id,:ws,:pid,:cat,:intent,:q,:sum,:data,:src,:ctx,:files,:tok,:bud,:dur,:st,:by)
                """), {"id":entry_id,"ws":workspace_id,"pid":project_id,"cat":category,"intent":intent,
                       "q":query,"sum":summary,"data":json.dumps(result_data) if result_data else None,
                       "src":json.dumps(sources_used) if sources_used else None,"ctx":context_assembled,
                       "files":json.dumps(files_changed) if files_changed else None,"tok":tokens_used,
                       "bud":tokens_budgeted,"dur":duration_seconds,"st":status,"by":created_by})
                await session.commit()
            return entry_id
        except Exception as e:
            logger.error("MEMORY: Record failed: %s", e)
            return ""

    async def search(self, workspace_id: str, query: str, categories: list[str] | None = None,
                     limit: int = 5) -> list[dict]:
        try:
            cat_filter, params = "", {"ws":workspace_id,"q":f"%{query}%","lim":limit}
            if categories:
                ph = ", ".join([f":cat{i}" for i in range(len(categories))])
                cat_filter = f"AND category IN ({ph})"
                for i,c in enumerate(categories): params[f"cat{i}"] = c
            async with async_session_factory() as session:
                r = await session.execute(text(f"""
                    SELECT id,category,query,summary,result_data,files_changed,tokens_used,status,created_at
                    FROM workspace_memory WHERE workspace_id=:ws {cat_filter}
                    AND (query LIKE :q OR summary LIKE :q) ORDER BY created_at DESC LIMIT :lim
                """), params)
                return [{"id":row[0],"category":row[1],"query":row[2],"summary":row[3],
                         "result_data":json.loads(row[4]) if row[4] else None,
                         "files_changed":json.loads(row[5]) if row[5] else None,
                         "tokens_used":row[6],"status":row[7],
                         "created_at":row[8].isoformat() if row[8] else None} for row in r.fetchall()]
        except Exception as e:
            logger.error("MEMORY: Search failed: %s", e)
            return []

    async def get_recent(self, workspace_id: str, limit: int = 20,
                         categories: list[str] | None = None) -> list[dict]:
        try:
            cat_filter, params = "", {"ws":workspace_id,"lim":limit}
            if categories:
                ph = ", ".join([f":cat{i}" for i in range(len(categories))])
                cat_filter = f"AND category IN ({ph})"
                for i,c in enumerate(categories): params[f"cat{i}"] = c
            async with async_session_factory() as session:
                r = await session.execute(text(f"""
                    SELECT id,category,query,summary,status,tokens_used,created_at
                    FROM workspace_memory WHERE workspace_id=:ws {cat_filter}
                    ORDER BY created_at DESC LIMIT :lim
                """), params)
                return [{"id":row[0],"category":row[1],"query":row[2],"summary":row[3],
                         "status":row[4],"tokens_used":row[5],
                         "created_at":row[6].isoformat() if row[6] else None} for row in r.fetchall()]
        except Exception as e:
            logger.error("MEMORY: Get recent failed: %s", e)
            return []

    async def get_events_since(self, workspace_id: str, since_hours: int = 24) -> list[dict]:
        try:
            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT id,category,query,summary,result_data,files_changed,status,created_at
                    FROM workspace_memory WHERE workspace_id=:ws
                    AND created_at > datetime('now', :since) ORDER BY created_at DESC
                """), {"ws":workspace_id,"since":f"-{since_hours} hours"})
                return [{"id":row[0],"category":row[1],"query":row[2],"summary":row[3],
                         "result_data":json.loads(row[4]) if row[4] else None,
                         "files_changed":json.loads(row[5]) if row[5] else None,
                         "status":row[6],"created_at":row[7].isoformat() if row[7] else None}
                        for row in r.fetchall()]
        except Exception as e:
            logger.error("MEMORY: Get events since failed: %s", e)
            return []

_memory = WorkspaceMemory()
def get_workspace_memory() -> WorkspaceMemory: return _memory
