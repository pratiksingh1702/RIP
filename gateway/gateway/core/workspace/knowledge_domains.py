"""Knowledge Domains — organized intelligence categories."""

from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class KnowledgeDomain:
    name: str
    description: str
    knowledge_types: list[str] = field(default_factory=list)

class KnowledgeDomains:
    """Seven domains that organize workspace knowledge."""
    
    DOMAINS = {
        "repository": KnowledgeDomain("Repository Knowledge",
            "Architecture, dependencies, ownership, health",
            ["architecture", "dependency", "ownership", "health", "structure"]),
        "architecture": KnowledgeDomain("Architecture Knowledge",
            "Design decisions, service boundaries, tech choices",
            ["decision", "design", "pattern", "technology", "migration"]),
        "execution": KnowledgeDomain("Execution Knowledge",
            "Agent runs, workflow history, success patterns",
            ["execution", "workflow", "test_result", "deployment", "verification"]),
        "team": KnowledgeDomain("Team Knowledge",
            "Expertise, collaboration, decision patterns",
            ["person", "team", "review", "collaboration"]),
        "operations": KnowledgeDomain("Operational Knowledge",
            "Deployments, incidents, postmortems, runbooks",
            ["deployment", "incident", "postmortem", "runbook", "monitoring"]),
        "ai": KnowledgeDomain("AI Knowledge",
            "Model performance, prompt patterns, cost optimization",
            ["model_performance", "prompt_pattern", "cost", "llm_selection"]),
        "organization": KnowledgeDomain("Organizational Knowledge",
            "Standards, reusable patterns, cross-project learnings",
            ["standard", "pattern", "learning", "policy", "convention"]),
    }
    
    def get_domain(self, knowledge_type: str) -> str:
        for domain_name, domain in self.DOMAINS.items():
            if knowledge_type in domain.knowledge_types:
                return domain_name
        return "repository"
    
    def list_domains(self) -> list[dict]:
        return [{"name": d.name, "description": d.description} for d in self.DOMAINS.values()]

_domains = KnowledgeDomains()
def get_knowledge_domains() -> KnowledgeDomains: return _domains
