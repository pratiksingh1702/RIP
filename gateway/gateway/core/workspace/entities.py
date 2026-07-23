"""Entity Graph — how everything connects: goals, decisions, PRs, people, files."""

from __future__ import annotations
import json, logging
from uuid import uuid4
from gateway.storage.database import async_session_factory
from sqlalchemy import text

logger = logging.getLogger(__name__)

class EntityGraph:
    """Stores entities and their relationships. Everything links together."""
    
    async def create_entity(self, workspace_id: str, entity_type: str, name: str,
                            attributes: dict | None = None) -> str:
        entity_id = str(uuid4())
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    INSERT INTO workspace_entities (id,workspace_id,entity_type,name,attributes)
                    VALUES (:id,:ws,:et,:n,:attr)
                """), {"id":entity_id,"ws":workspace_id,"et":entity_type,"n":name,
                       "attr":json.dumps(attributes) if attributes else None})
                await session.commit()
            return entity_id
        except Exception as e:
            logger.error("ENTITIES: Create failed: %s", e)
            return ""

    async def link(self, workspace_id: str, source_id: str, target_id: str,
                   relationship_type: str) -> str:
        rel_id = str(uuid4())
        try:
            async with async_session_factory() as session:
                await session.execute(text("""
                    INSERT INTO entity_relationships (id,workspace_id,source_entity_id,
                    target_entity_id,relationship_type) VALUES (:id,:ws,:src,:tgt,:rt)
                """), {"id":rel_id,"ws":workspace_id,"src":source_id,"tgt":target_id,"rt":relationship_type})
                await session.commit()
            return rel_id
        except Exception as e:
            logger.error("ENTITIES: Link failed: %s", e)
            return ""

    async def get_related(self, workspace_id: str, entity_id: str) -> list[dict]:
        try:
            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT e.id,e.entity_type,e.name,e.attributes,er.relationship_type
                    FROM workspace_entities e JOIN entity_relationships er ON e.id=er.target_entity_id
                    WHERE er.workspace_id=:ws AND er.source_entity_id=:eid
                    UNION
                    SELECT e.id,e.entity_type,e.name,e.attributes,er.relationship_type
                    FROM workspace_entities e JOIN entity_relationships er ON e.id=er.source_entity_id
                    WHERE er.workspace_id=:ws AND er.target_entity_id=:eid
                """), {"ws":workspace_id,"eid":entity_id})
                return [{"id":row[0],"entity_type":row[1],"name":row[2],
                         "attributes":json.loads(row[3]) if row[3] else None,
                         "relationship":row[4]} for row in r.fetchall()]
        except Exception as e:
            logger.error("ENTITIES: Get related failed: %s", e)
            return []

    async def get_by_type(self, workspace_id: str, entity_type: str) -> list[dict]:
        try:
            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT id,name,attributes,created_at FROM workspace_entities
                    WHERE workspace_id=:ws AND entity_type=:et ORDER BY created_at DESC
                """), {"ws":workspace_id,"et":entity_type})
                return [{"id":row[0],"name":row[1],
                         "attributes":json.loads(row[2]) if row[2] else None,
                         "created_at":row[3].isoformat() if row[3] else None} for row in r.fetchall()]
        except Exception as e:
            logger.error("ENTITIES: Get by type failed: %s", e)
            return []

_entities = EntityGraph()
def get_entity_graph() -> EntityGraph: return _entities
