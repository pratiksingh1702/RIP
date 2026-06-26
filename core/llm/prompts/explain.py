"""Explain prompt templates - language and framework agnostic."""

from __future__ import annotations

EXPLAIN_SYSTEM_PROMPT = """You are an expert software architect and senior developer.
You explain codebases the way a senior engineer would onboard a new team member.

Rules:
- Focus on ARCHITECTURE, WORKFLOW, and DEPENDENCIES — NOT individual variables, UI widgets, or language primitives.
- Never explain: getters, setters, builders, constructors, FocusNode, TextEditingController, BuildContext, 
  props, state variables, HTML elements, CSS classes, or private helpers.
- Explain HOW components connect and data flows, not WHAT each line of code does.
- Use the provided dependency graph, workflow chain, and relationships to structure your answer.
- Adapt your explanation to the language/framework shown in the context (don't assume Flutter/Dart).
- Be concise and technical. Output in Markdown.
- If the context shows a web framework, talk about routes/controllers/middleware.
- If the context shows a mobile app, talk about screens/providers/repositories.
- If the context shows a backend service, talk about services/repositories/API endpoints.
- If the context shows a CLI tool, talk about commands/parsers/handlers.
"""

EXPLAIN_FLOW_PROMPT = """Explain how **{query}** works in this codebase.

Trace the flow from entry point through all connected components.

{context}

Structure your answer as:
1. **Overview** — One sentence summary of what this flow accomplishes
2. **Workflow** — Step-by-step data/control flow (Component1 → Component2 → Component3)
3. **Key Components** — What each component does in the chain
4. **Data Flow** — How data moves through the system (request → process → response, or input → state → UI)
5. **Entry & Exit Points** — Where the flow starts and ends
6. **Important Files** — Key files to understand this flow
"""

EXPLAIN_ARCHITECTURE_PROMPT = """Explain the architecture of **{query}** in this codebase.

{context}

Structure your answer as:
1. **Overview** — What this module/feature/component does
2. **Architecture Pattern** — What pattern is used (MVC, Clean Architecture, Feature-based, Layered, Microservice, etc.)
3. **Component Breakdown** — Key components and their responsibilities
4. **Dependency Map** — How components depend on each other
5. **Data Layer** — How data is stored, accessed, and cached
6. **Communication Patterns** — How components communicate (HTTP, events, message queues, direct calls)
7. **File Organization** — Where things are located
"""

EXPLAIN_API_PROMPT = """Explain the API structure for **{query}** in this codebase.

{context}

Structure your answer as:
1. **Overview** — What APIs/services are involved
2. **Request Flow** — How requests flow through the system
3. **Endpoints / Routes** — Key endpoints, routes, or RPC methods
4. **Request/Response Patterns** — Common request/response shapes
5. **Authentication/Authorization** — How access is controlled (if visible)
6. **Error Handling** — How errors propagate
7. **Client Consumption** — How clients consume these APIs
"""

EXPLAIN_STATE_PROMPT = """Explain the state and data management for **{query}** in this codebase.

{context}

Structure your answer as:
1. **Overview** — What state/data is managed
2. **State Flow** — How state changes propagate through the system
3. **State Sources** — Where state originates (user input, API, database, events)
4. **State Consumers** — What components react to state changes
5. **Persistence** — How state is persisted (if applicable)
6. **Synchronization** — How state stays consistent across components
"""

EXPLAIN_DEPENDENCY_PROMPT = """Explain the dependencies for **{query}** in this codebase.

{context}

Structure your answer as:
1. **Overview** — What this component depends on
2. **Upstream Dependencies** — What calls/uses this component
3. **Downstream Dependencies** — What this component calls/uses
4. **Impact Analysis** — What breaks if this changes
5. **Coupling Level** — How tightly coupled this is
"""

EXPLAIN_DEFAULT_PROMPT = """Explain **{query}** based on the collected context:

{context}

Provide a technical explanation covering:
1. **What It Is** — Purpose and responsibility
2. **Architectural Role** — How it fits in the bigger picture
3. **Key Relationships** — What it depends on and what depends on it
4. **Important Details** — Any notable patterns, edge cases, or design decisions
"""


def get_explain_prompt(intent: str, query: str, context: str) -> tuple[str, str]:
    """Get the appropriate system and user prompts based on detected intent.
    
    Args:
        intent: One of 'flow', 'architecture', 'api', 'state', 'dependency', 'semantic'
        query: The user's original query
        context: The assembled context string
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    intent_map = {
        "flow": EXPLAIN_FLOW_PROMPT,
        "architecture": EXPLAIN_ARCHITECTURE_PROMPT,
        "api": EXPLAIN_API_PROMPT,
        "state": EXPLAIN_STATE_PROMPT,
        "dependency": EXPLAIN_DEPENDENCY_PROMPT,
    }
    user_prompt = intent_map.get(intent, EXPLAIN_DEFAULT_PROMPT).format(query=query, context=context)
    return EXPLAIN_SYSTEM_PROMPT, user_prompt