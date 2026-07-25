"""Provenance Tagging — tags all content with source and trust level."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class TrustLevel(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    UNKNOWN = "unknown"

@dataclass
class ContentProvenance:
    source: str
    trust: TrustLevel
    content_type: str = "data"
    metadata: dict | None = None

    def wrap(self, content: str) -> str:
        """Wrap content with provenance markers so the LLM knows it's data, not instructions."""
        return f'[DATA from {self.source} | trust={self.trust.value} | type={self.content_type}]\n{content}\n[/DATA]'

    def to_dict(self) -> dict:
        return {"source": self.source, "trust": self.trust.value, "content_type": self.content_type, "metadata": self.metadata}

TRUSTED_SOURCES = {"rip", "workspace_memory", "workspace_knowledge", "workspace_goals", "entity_graph"}
EXTERNAL_SOURCES = {"github", "jira", "slack", "gitlab", "linear", "notion"}

class ProvenanceTagger:
    """Tags content with source provenance and trust level."""

    def tag(self, source: str, content: str, content_type: str = "data", metadata: dict | None = None) -> ContentProvenance:
        trust = TrustLevel.INTERNAL if source in TRUSTED_SOURCES else (TrustLevel.EXTERNAL if source in EXTERNAL_SOURCES else TrustLevel.UNKNOWN)
        return ContentProvenance(source=source, trust=trust, content_type=content_type, metadata=metadata)

    def tag_and_wrap(self, source: str, content: str, content_type: str = "data") -> str:
        prov = self.tag(source, content, content_type)
        return prov.wrap(content)

    def tag_all(self, items: list[dict]) -> list[dict]:
        """Tag a list of context items with provenance."""
        tagged = []
        for item in items:
            source = item.get("source", "unknown")
            prov = self.tag(source, item.get("content", ""))
            tagged.append({**item, "provenance": prov.to_dict(), "content": prov.wrap(item.get("content", ""))})
        return tagged

_tagger: ProvenanceTagger | None = None
def get_provenance_tagger() -> ProvenanceTagger:
    global _tagger
    if _tagger is None:
        _tagger = ProvenanceTagger()
    return _tagger
