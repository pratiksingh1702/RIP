"""Workspace module — knowledge, memory, goals, entities, intelligence, injection, privacy."""
from gateway.core.workspace.memory import WorkspaceMemory, get_workspace_memory
from gateway.core.workspace.knowledge import WorkspaceKnowledge, get_workspace_knowledge
from gateway.core.workspace.goals import GoalEngine, get_goal_engine
from gateway.core.workspace.entities import EntityGraph, get_entity_graph
from gateway.core.workspace.state import WorkspaceState, get_workspace_state
from gateway.core.workspace.router import WorkspaceRouter, get_workspace_router
from gateway.core.workspace.capabilities import CapabilityRegistry, get_capability_registry
from gateway.core.workspace.knowledge_scoring import compute_confidence, ConfidenceTier, get_surfacing_rule
from gateway.core.workspace.knowledge_engine import KnowledgeIntelligenceEngine, get_knowledge_engine
from gateway.core.workspace.knowledge_domains import KnowledgeDomains, get_knowledge_domains
from gateway.core.workspace.knowledge_lifecycle import KnowledgeLifecycle, get_knowledge_lifecycle
from gateway.core.workspace.context_injector import ContextInjector, get_context_injector
from gateway.core.workspace.knowledge_extractor import KnowledgeExtractor, get_knowledge_extractor
from gateway.core.workspace.privacy import PrivacyEngine, get_privacy_engine

__all__ = [
    "WorkspaceMemory", "get_workspace_memory",
    "WorkspaceKnowledge", "get_workspace_knowledge",
    "GoalEngine", "get_goal_engine",
    "EntityGraph", "get_entity_graph",
    "WorkspaceState", "get_workspace_state",
    "WorkspaceRouter", "get_workspace_router",
    "CapabilityRegistry", "get_capability_registry",
    "compute_confidence", "ConfidenceTier", "get_surfacing_rule",
    "KnowledgeIntelligenceEngine", "get_knowledge_engine",
    "KnowledgeDomains", "get_knowledge_domains",
    "KnowledgeLifecycle", "get_knowledge_lifecycle",
    "ContextInjector", "get_context_injector",
    "KnowledgeExtractor", "get_knowledge_extractor",
    "PrivacyEngine", "get_privacy_engine",
]
