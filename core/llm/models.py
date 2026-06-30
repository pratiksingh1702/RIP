"""LLM models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field, AliasChoices


class ExplainIntent(str, Enum):
    """Detected intent for explanation."""
    FLOW = "flow"              # "How X works", workflow, process
    ARCHITECTURE = "architecture"  # "Architecture of X", structure, modules
    API = "api"                # "API flow", endpoints, request/response
    STATE = "state"            # "State management", provider, notifier
    DEPENDENCY = "dependency"  # "Dependencies of X", imports, callers
    SEMANTIC = "semantic"      # Default: semantic search-based


@dataclass
class ExplainContext:
    """Rich architectural context for LLM explanation."""
    query: str
    intent: ExplainIntent = ExplainIntent.SEMANTIC
    feature: str | None = None
    
    # Workflow chain (entry → exit)
    entry_points: list[dict] = field(default_factory=list)
    workflow_chain: list[dict] = field(default_factory=list)
    
    # Dependency graph
    dependency_graph: dict[str, list[tuple[str, str]]] = field(default_factory=dict)  # {entity: [(dep, rel_type)]}
    
    # State flow
    state_providers: list[dict] = field(default_factory=list)
    state_flow: list[dict] = field(default_factory=list)
    
    # API flow
    api_endpoints: list[dict] = field(default_factory=list)
    api_chain: list[dict] = field(default_factory=list)
    
    # Widget tree (Flutter)
    widget_tree: dict[str, list[str]] | None = None
    
    # Important files & entities
    important_files: list[str] = field(default_factory=list)
    imported_files: list[dict] = field(default_factory=list)
    important_entities: list[dict] = field(default_factory=list)
    
    # Overview & suggestions
    overview: str = ""
    suggestions: list[str] = field(default_factory=list)
    
    # Raw context string (for LLM)
    context_str: str = ""
    found: bool = False


class ExplanationRequest(BaseModel):
    """Request for code symbol explanation."""
    symbol: str = Field(
        ...,
        validation_alias=AliasChoices("symbol", "query"),
        description="The symbol (function, class, etc.) to explain",
    )
    context_level: str = Field("file", description="Context scope: 'file', 'class', or 'function'")
    provider: str | None = Field(None, description="Optional: LLM provider to use")
    model: str | None = Field(None, description="Optional: LLM model to use")
    project_id: str | None = Field(None, description="Project id to explain within")
    repo_path: str | None = Field(
        None,
        description="Optional repository path used to resolve .repo-intel active project",
    )
    diagram: bool = Field(False, description="Show Mermaid workflow diagram")
    tree: bool = Field(
        False,
        validation_alias=AliasChoices("tree", "tree_view"),
        description="Show workflow tree",
    )
    dependencies: bool = Field(
        False,
        validation_alias=AliasChoices("dependencies", "deps"),
        description="Show dependency table",
    )
    code: bool = Field(False, description="Show relevant indexed code snippets")
    no_llm: bool = Field(False, description="Skip LLM and return graph context only")
    max_hops: int = Field(8, description="Maximum workflow trace hops")


class ExplanationResponse(BaseModel):
    """Response containing symbol explanation and suggested improvements."""
    explanation: str = Field(..., description="Detailed explanation of the symbol")
    suggested_improvements: list[str] = Field(default_factory=list)
