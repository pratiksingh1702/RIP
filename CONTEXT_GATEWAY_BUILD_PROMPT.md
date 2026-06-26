# Context Gateway — Complete Agent Build Prompt
## Full Plan, Explanation, and Task List

---

## READ THIS ENTIRE DOCUMENT BEFORE WRITING A SINGLE LINE OF CODE

You are building the Context Gateway — Phase 2 of the Repository Intelligence Platform. Phase 1 (RIP Core) is already complete and working. The Context Gateway sits on top of RIP and orchestrates everything between AI coding agents and all data sources.

This document is your complete specification. It contains the architecture, the exact file structure, the data flow, every component explained in detail, the database schemas, the MCP tool contracts, and a day-by-day build plan. Do not guess at anything. If something is unclear, re-read the relevant section before proceeding.

---

## WHAT YOU ARE BUILDING AND WHY

### The Problem That Still Exists After RIP

RIP is complete. The graph is built. The vectors are stored. `repo trace`, `repo impact`, `repo search` all work correctly.

But when Claude Code or Codex uses RIP today, the agent has to make all the decisions itself. It has to decide which RIP tool to call. It has to decide whether to also check GitHub for open PRs. It has to figure out that the Jira ticket contains the acceptance criteria. It might call five tools that return overlapping information. It might not know another developer is simultaneously modifying the same files. It wastes tokens on irrelevant context because nothing is filtering or ranking results.

RIP solved the **intelligence problem** — it knows everything about the codebase. The Context Gateway solves the **orchestration problem** — it decides what to retrieve, from where, in what order, and how much to give the agent.

### What the Context Gateway Does

When an agent asks "I need context for adding retry logic to the payment service," the gateway:

1. Classifies the intent — feature addition, payment domain, medium risk
2. Plans which sources to query — RIP trace, RIP search, GitHub recent PRs, Jira ticket
3. Executes all queries in parallel — everything runs simultaneously, not sequentially
4. Ranks results by relevance — the existing retry pattern in http_client.py scores highest
5. Compresses to fit the token budget — 28,000 raw tokens becomes 11,300 targeted tokens
6. Checks for conflicts — another session is touching StripeAdapter, inject a warning
7. Filters by permissions — agent role determines what it can see
8. Returns one clean package — agent starts working immediately with perfect context

The agent makes one tool call. The gateway handles everything else.

### The Two Numbers That Matter

**60× token reduction** — Without RIP and gateway, an agent reads files iteratively and uses 85,000 to 120,000 tokens for a typical task. With RIP + Context Gateway, the same task uses 8,000 to 15,000 tokens. Same quality, 60× fewer tokens.

**1.2 seconds latency** — All source queries run in parallel. Four sources queried simultaneously complete in the time of the slowest single query, not the sum of all queries.

---

## ARCHITECTURE — THE TWO TIERS

The system has two tiers connected through the gateway.

```
┌──────────────────────────────────────────────────────────────┐
│                    TIER 1 — AI AGENTS                        │
│  Claude Code · Codex · Cursor · Gemini CLI · Any MCP agent   │
│                                                              │
│  These see only 4 clean tools:                               │
│  get_context · validate_change · search_codebase             │
│  explain_architecture                                        │
└──────────────────────────┬───────────────────────────────────┘
                           │ MCP Protocol (stdio)
                           │ One call in, one package out
┌──────────────────────────▼───────────────────────────────────┐
│                   CONTEXT GATEWAY                             │
│                                                              │
│  Classifier → Planner → Executor → Ranker → Memory → Filter  │
│                                                              │
│  This is what you are building.                              │
└──────────────────────────┬───────────────────────────────────┘
                           │ MCP Client calls (Tier 2)
                           │ Multiple sources, parallel
┌──────────────────────────┼───────────────────────────────────┐
│   RIP MCP    GitHub MCP    Jira MCP    Slack MCP    Others   │
│   (built)    (external)  (external)  (external)   (future)  │
└──────────────────────────────────────────────────────────────┘
```

Agents in Tier 1 never change when you add new data sources. Data sources in Tier 2 never change when you add new agents. The gateway is the stable middle layer.

---

## FILE STRUCTURE — CREATE THIS SKELETON FIRST

Create every file listed below as an empty stub before writing any implementation. This prevents structure drift.

```
gateway/
├── README.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── alembic.ini
│
├── gateway/
│   ├── __init__.py
│   ├── config.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   │
│   │   ├── classifier/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── rules.py
│   │   │   ├── few_shot.py
│   │   │   ├── models.py
│   │   │   └── patterns.py
│   │   │
│   │   ├── planner/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── strategies.py
│   │   │   ├── optimizer.py
│   │   │   ├── models.py
│   │   │   └── budget.py
│   │   │
│   │   ├── executor/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── circuit_breaker.py
│   │   │   ├── retry.py
│   │   │   └── models.py
│   │   │
│   │   ├── ranker/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── compressor.py
│   │   │   ├── deduplicator.py
│   │   │   ├── summarizer.py
│   │   │   ├── models.py
│   │   │   └── scorers/
│   │   │       ├── __init__.py
│   │   │       ├── semantic.py
│   │   │       ├── centrality.py
│   │   │       ├── recency.py
│   │   │       ├── pattern.py
│   │   │       └── authority.py
│   │   │
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── store.py
│   │   │   ├── conflict_detector.py
│   │   │   ├── context_bridge.py
│   │   │   ├── learning.py
│   │   │   └── models.py
│   │   │
│   │   ├── permissions/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── roles.py
│   │   │   ├── policies.py
│   │   │   ├── audit.py
│   │   │   └── models.py
│   │   │
│   │   ├── sources/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── rip_client.py
│   │   │   ├── github_client.py
│   │   │   ├── jira_client.py
│   │   │   ├── slack_client.py
│   │   │   └── models.py
│   │   │
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── models.py
│   │   │   └── prompts/
│   │   │       ├── __init__.py
│   │   │       ├── classifier.py
│   │   │       ├── ranker.py
│   │   │       ├── summarizer.py
│   │   │       └── conflict.py
│   │   │
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   └── engine.py
│   │   │
│   │   ├── tokenizer/
│   │   │   ├── __init__.py
│   │   │   ├── counter.py
│   │   │   ├── budget.py
│   │   │   └── models.py
│   │   │
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   ├── redis_store.py
│   │   │   ├── local_store.py
│   │   │   └── models.py
│   │   │
│   │   └── metrics/
│   │       ├── __init__.py
│   │       ├── collector.py
│   │       ├── models.py
│   │       └── exporter.py
│   │
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── tools.py
│   │   ├── handlers.py
│   │   └── middleware.py
│   │
│   ├── server/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── rate_limit.py
│   │   │   ├── logging.py
│   │   │   └── cors.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── context.py
│   │   │   ├── validate.py
│   │   │   ├── sessions.py
│   │   │   ├── sources.py
│   │   │   ├── metrics.py
│   │   │   └── health.py
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── requests.py
│   │       ├── responses.py
│   │       └── common.py
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── start.py
│   │       ├── status.py
│   │       ├── sources.py
│   │       ├── config.py
│   │       └── mcp.py
│   │
│   └── storage/
│       ├── __init__.py
│       ├── database.py
│       ├── models.py
│       └── migrations/
│           ├── env.py
│           └── versions/
│               └── 001_initial.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_classifier.py
│   │   ├── test_planner.py
│   │   ├── test_executor.py
│   │   ├── test_ranker.py
│   │   ├── test_compressor.py
│   │   ├── test_memory.py
│   │   ├── test_permissions.py
│   │   └── test_tokenizer.py
│   ├── integration/
│   │   ├── test_full_pipeline.py
│   │   ├── test_mcp_server.py
│   │   ├── test_conflict_detection.py
│   │   └── test_session_bridging.py
│   └── performance/
│       ├── test_parallel_execution.py
│       ├── test_cache_hits.py
│       └── test_large_repo.py
│
├── docs/
│   ├── architecture.md
│   ├── setup.md
│   ├── api.md
│   ├── mcp.md
│   ├── sources.md
│   └── operations.md
│
└── scripts/
    ├── setup.sh
    ├── migrate.sh
    └── benchmark.sh
```

---

## DEPENDENCIES — ADD TO pyproject.toml

```toml
[project]
name = "context-gateway"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # Core
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "typer[all]>=0.12.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    
    # Database
    "sqlalchemy[asyncio]>=2.0.0",
    "alembic>=1.13.0",
    "asyncpg>=0.29.0",
    "redis[asyncio]>=5.0.0",
    
    # MCP
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    
    # ML
    "sentence-transformers>=3.0.0",
    "tiktoken>=0.7.0",
    "numpy>=1.26.0",
    
    # LLM
    "litellm>=1.40.0",
    
    # Utilities
    "structlog>=24.0.0",
    "rich>=13.7.0",
    "python-dotenv>=1.0.0",
    "orjson>=3.10.0",
]

[project.scripts]
gateway = "gateway.cli.main:app"
```

---

## THE FOUR MCP TOOLS — TIER 1 INTERFACE

These are the only four things AI agents ever see. Implement these contracts exactly.

### Tool 1: `get_context`
```python
{
    "name": "get_context",
    "description": (
        "Get complete context for a coding task. ALWAYS call this before "
        "starting any code modification. Returns ranked, compressed context "
        "from the codebase, open PRs, tickets, and team discussions. "
        "Automatically detects conflicts with other active sessions."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Full description of what you need to do"
            },
            "max_tokens": {
                "type": "integer",
                "description": "Maximum context tokens to return",
                "default": 12000
            },
            "role": {
                "type": "string",
                "description": "Agent role for permission filtering",
                "default": "developer",
                "enum": ["junior_dev", "developer", "senior_dev", "ci_agent"]
            }
        },
        "required": ["task"]
    }
}
```

### Tool 2: `validate_change`
```python
{
    "name": "validate_change",
    "description": (
        "Check if a code change will break anything. Run this BEFORE "
        "applying any patch. Returns impact analysis, affected tests, "
        "downstream services at risk, and breaking change detection."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "diff": {
                "type": "string",
                "description": "The git diff or code change to validate"
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific files being changed"
            }
        },
        "required": ["diff"]
    }
}
```

### Tool 3: `search_codebase`
```python
{
    "name": "search_codebase",
    "description": (
        "Semantic search across the codebase by meaning. "
        "Finds code by what it does, not just keywords. "
        "Use when you need to find where something is implemented."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results",
                "default": 10
            }
        },
        "required": ["query"]
    }
}
```

### Tool 4: `explain_architecture`
```python
{
    "name": "explain_architecture",
    "description": (
        "Get architectural explanation with call chains and dependency maps. "
        "Use when you need to understand how a system or feature works "
        "before making changes to it."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "What to explain (service, feature, or module name)"
            },
            "include_diagrams": {
                "type": "boolean",
                "description": "Include Mermaid diagrams in response",
                "default": True
            }
        },
        "required": ["topic"]
    }
}
```

---

## DATABASE SCHEMA — IMPLEMENT EXACTLY AS WRITTEN

Run Alembic migrations. Do not hand-create tables.

```sql
-- sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type VARCHAR(50) NOT NULL,
    task_description TEXT NOT NULL,
    intent VARCHAR(50) NOT NULL,
    domain VARCHAR(100),
    risk_level VARCHAR(20),
    files_accessed TEXT[] DEFAULT '{}',
    nodes_accessed TEXT[] DEFAULT '{}',
    sources_used TEXT[] DEFAULT '{}',
    tokens_retrieved INTEGER DEFAULT 0,
    tokens_delivered INTEGER DEFAULT 0,
    tokens_saved INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'in_progress',
    outcome TEXT,
    files_modified TEXT[] DEFAULT '{}',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    git_branch VARCHAR(255),
    project_id UUID,
    user_id VARCHAR(255)
);

-- session events for analytics
CREATE TABLE session_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    data JSONB,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- feedback for learning loop
CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    was_helpful BOOLEAN,
    missing_context TEXT[],
    irrelevant_context TEXT[],
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- source health tracking
CREATE TABLE source_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR(100) NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    avg_latency_ms INTEGER,
    error_rate FLOAT DEFAULT 0.0,
    last_checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- performance indexes
CREATE INDEX idx_sessions_active ON sessions(status) WHERE status = 'in_progress';
CREATE INDEX idx_sessions_files ON sessions USING GIN(files_accessed);
CREATE INDEX idx_sessions_domain ON sessions(domain);
CREATE INDEX idx_sessions_agent ON sessions(agent_type, started_at DESC);
CREATE INDEX idx_events_session ON session_events(session_id, created_at DESC);
CREATE INDEX idx_feedback_session ON feedback(session_id);
```

---

## COMPONENT-BY-COMPONENT BUILD INSTRUCTIONS

---

### COMPONENT 1 — INTENT CLASSIFIER

**What it does:** Reads the agent's task description and determines what type of work this is, what domain it affects, and what risk level it carries.

**File:** `gateway/core/classifier/engine.py`

**The classifier pipeline:**
1. First run rule-based patterns — fast, free, handles 80% of cases
2. If confidence below 0.70, call LLM with few-shot examples
3. Return a `ClassificationResult` with intent, confidence, domain, risk

**Intent types to support:**
- `bug_fix` — fixing something broken
- `feature_addition` — adding new functionality
- `refactor` — restructuring existing code without changing behavior
- `architectural_question` — understanding how something works
- `investigation` — debugging or exploring behavior
- `documentation` — writing or updating docs

**Domain detection keywords:**
```python
DOMAIN_PATTERNS = {
    "payment": ["payment", "stripe", "charge", "invoice", "billing", "refund", "transaction"],
    "auth": ["auth", "login", "jwt", "token", "session", "permission", "oauth", "password"],
    "api": ["endpoint", "route", "request", "response", "http", "rest", "graphql"],
    "database": ["query", "migration", "schema", "model", "orm", "repository", "table"],
    "notification": ["email", "sms", "push", "notification", "webhook", "event"],
    "infrastructure": ["deploy", "docker", "kubernetes", "ci", "pipeline", "server"],
}
```

**Risk level logic:**
- `high` — touching authentication, payment processing, database migrations, public APIs
- `medium` — modifying code that other services depend on
- `low` — isolated utilities, tests, documentation, configuration

**`ClassificationResult` Pydantic model:**
```python
from pydantic import BaseModel
from enum import Enum

class IntentType(str, Enum):
    BUG_FIX = "bug_fix"
    FEATURE_ADDITION = "feature_addition"
    REFACTOR = "refactor"
    ARCHITECTURAL_QUESTION = "architectural_question"
    INVESTIGATION = "investigation"
    DOCUMENTATION = "documentation"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ClassificationResult(BaseModel):
    intent: IntentType
    confidence: float          # 0.0 to 1.0
    domain: str                # "payment", "auth", etc.
    risk_level: RiskLevel
    strategy: str              # "rules" or "llm_fallback"
    domain_keywords_found: list[str]
    raw_task: str
```

**Verification test after building:**
```python
# These must all classify correctly:
assert classify("Fix the null pointer in payment flow").intent == "bug_fix"
assert classify("Add retry logic to Stripe integration").intent == "feature_addition"
assert classify("How does authentication work?").intent == "architectural_question"
assert classify("Refactor UserService to use repository pattern").intent == "refactor"
```

---

### COMPONENT 2 — MULTI-SOURCE PLANNER

**What it does:** Takes the classification result and decides which sources to query, what to ask each source, in what order, and how to allocate the token budget across sources.

**File:** `gateway/core/planner/engine.py`

**The strategy table — this is the heart of the planner:**

```python
# gateway/core/planner/strategies.py

STRATEGY_TABLE = {
    IntentType.BUG_FIX: {
        "always_query": [
            {"source": "rip", "type": "trace", "description": "call chain around the error"},
            {"source": "rip", "type": "search", "description": "similar error handling patterns"},
            {"source": "github", "type": "recent_commits", "description": "files changed recently"},
        ],
        "conditional_query": [
            {
                "source": "github",
                "type": "open_prs",
                "condition": "files_overlap_with_active_prs",
                "description": "open PRs touching same files"
            },
            {
                "source": "jira",
                "type": "ticket",
                "condition": "ticket_number_in_task",
                "description": "bug report ticket"
            },
        ],
        "skip": ["slack"],
        "token_weights": {"rip": 0.55, "github": 0.30, "jira": 0.15},
        "recency_boost": True,  # recent changes more relevant for bugs
    },
    
    IntentType.FEATURE_ADDITION: {
        "always_query": [
            {"source": "rip", "type": "architecture", "description": "existing patterns"},
            {"source": "rip", "type": "search", "description": "similar existing implementations"},
            {"source": "rip", "type": "impact", "description": "what will be affected"},
        ],
        "conditional_query": [
            {
                "source": "jira",
                "type": "ticket",
                "condition": "ticket_number_in_task",
                "description": "feature requirements and acceptance criteria"
            },
            {
                "source": "github",
                "type": "similar_prs",
                "condition": "always",
                "description": "similar features implemented before"
            },
        ],
        "skip": ["slack"],
        "token_weights": {"rip": 0.50, "github": 0.25, "jira": 0.25},
        "recency_boost": False,
    },
    
    IntentType.ARCHITECTURAL_QUESTION: {
        "always_query": [
            {"source": "rip", "type": "architecture", "description": "full architecture map"},
            {"source": "rip", "type": "trace", "description": "call chains"},
            {"source": "rip", "type": "decisions", "description": "architectural decisions"},
        ],
        "conditional_query": [
            {
                "source": "slack",
                "type": "search",
                "condition": "always",  # WHY questions always benefit from Slack history
                "description": "team discussions about this area"
            },
            {
                "source": "github",
                "type": "pr_descriptions",
                "condition": "always",
                "description": "PR descriptions explaining design choices"
            },
        ],
        "skip": [],
        "token_weights": {"rip": 0.45, "github": 0.25, "slack": 0.30},
        "recency_boost": False,
    },
    
    IntentType.REFACTOR: {
        "always_query": [
            {"source": "rip", "type": "impact", "description": "everything that depends on target"},
            {"source": "rip", "type": "coupling", "description": "coupling and cohesion metrics"},
            {"source": "rip", "type": "search", "description": "existing patterns to match"},
        ],
        "conditional_query": [
            {
                "source": "github",
                "type": "recent_commits",
                "condition": "always",
                "description": "recent changes to affected files"
            },
        ],
        "skip": ["slack", "jira"],
        "token_weights": {"rip": 0.70, "github": 0.30},
        "recency_boost": False,
    },
}
```

**`Plan` Pydantic model:**
```python
class SourceQuery(BaseModel):
    source: str              # "rip", "github", "jira", "slack"
    query_type: str          # "trace", "search", "architecture", "impact" etc.
    query_params: dict       # Parameters for the query
    priority: int            # 1=critical, 2=important, 3=nice-to-have
    estimated_tokens: int    # Expected token count for response
    timeout_seconds: float = 3.0

class RetrievalStep(BaseModel):
    queries: list[SourceQuery]
    parallel: bool = True
    condition: str = "always"   # When to execute this step

class Plan(BaseModel):
    classification: ClassificationResult
    steps: list[RetrievalStep]
    token_budget: int
    token_allocation: dict[str, int]  # source -> token budget
    estimated_tokens_raw: int
    created_at: datetime
```

---

### COMPONENT 3 — PARALLEL EXECUTOR

**What it does:** Takes the plan and executes all source queries, running them simultaneously with timeout protection and circuit breaking.

**File:** `gateway/core/executor/engine.py`

**The execution pattern:**
```python
async def execute(self, plan: Plan) -> list[SourceResponse]:
    """Execute all queries in plan with parallel execution and timeout protection."""
    
    all_responses = []
    
    for step in plan.steps:
        if not self._should_execute_step(step):
            continue
        
        if step.parallel:
            # Run all queries in this step simultaneously
            tasks = [
                self._execute_single_query(query)
                for query in step.queries
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Run sequentially for conditional steps
            responses = []
            for query in step.queries:
                response = await self._execute_single_query(query)
                responses.append(response)
        
        # Filter out exceptions — failed sources should not block the response
        for resp in responses:
            if isinstance(resp, Exception):
                logger.warning("Source query failed", error=str(resp))
            else:
                all_responses.append(resp)
    
    return all_responses
```

**Circuit breaker — prevent cascading failures:**
```python
# gateway/core/executor/circuit_breaker.py

class CircuitBreaker:
    """
    If a source fails 3 times in 60 seconds, stop calling it for 5 minutes.
    Prevents a slow/down source from blocking the entire gateway.
    """
    FAILURE_THRESHOLD = 3
    RESET_TIMEOUT_SECONDS = 300  # 5 minutes
    WINDOW_SECONDS = 60
    
    def __init__(self):
        self._failures: dict[str, list[datetime]] = {}
        self._open_until: dict[str, datetime] = {}
    
    def is_open(self, source_name: str) -> bool:
        """Return True if circuit is open (source should not be called)."""
        if source_name in self._open_until:
            if datetime.utcnow() < self._open_until[source_name]:
                return True
            else:
                del self._open_until[source_name]
        return False
    
    def record_failure(self, source_name: str) -> None:
        """Record a failure. Open circuit if threshold exceeded."""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.WINDOW_SECONDS)
        
        if source_name not in self._failures:
            self._failures[source_name] = []
        
        self._failures[source_name] = [
            t for t in self._failures[source_name]
            if t > window_start
        ]
        self._failures[source_name].append(now)
        
        if len(self._failures[source_name]) >= self.FAILURE_THRESHOLD:
            self._open_until[source_name] = (
                now + timedelta(seconds=self.RESET_TIMEOUT_SECONDS)
            )
            logger.warning(
                "Circuit breaker opened",
                source=source_name,
                reset_at=self._open_until[source_name]
            )
```

**`SourceResponse` model:**
```python
class SourceResponse(BaseModel):
    source: str
    query_type: str
    content: str           # Raw text content
    metadata: dict         # Source-specific metadata
    token_count: int
    latency_ms: int
    success: bool
    error: str | None = None
```

---

### COMPONENT 4 — CONTEXT RANKER

**What it does:** Takes all raw source responses and scores every item by relevance to the specific task. Then fills the token budget with the highest-scoring items.

**File:** `gateway/core/ranker/engine.py`

**The five scoring dimensions:**

**1. Semantic similarity (30% weight)**
```python
# gateway/core/ranker/scorers/semantic.py

async def score(self, task_embedding: list[float], item_text: str) -> float:
    """Cosine similarity between task embedding and item embedding."""
    item_embedding = await self.embedder.embed(item_text)
    return float(np.dot(task_embedding, item_embedding) / (
        np.linalg.norm(task_embedding) * np.linalg.norm(item_embedding)
    ))
```

**2. Graph centrality (25% weight)**
```python
# gateway/core/ranker/scorers/centrality.py

async def score(self, item_metadata: dict) -> float:
    """
    Items from highly-connected nodes in the RIP graph score higher.
    A function called from 20 places is more architecturally important
    than a function called from 1 place.
    """
    node_id = item_metadata.get("fqn") or item_metadata.get("file_path")
    if not node_id:
        return 0.5  # neutral score for non-graph items
    
    # Query RIP for centrality of this node
    centrality = await self.rip_client.get_node_centrality(node_id)
    # Normalize to 0-1
    return min(1.0, centrality / 50.0)
```

**3. Recency (20% weight)**
```python
# gateway/core/ranker/scorers/recency.py

def score(self, item_metadata: dict, intent: IntentType) -> float:
    """
    Recently changed items score higher for bug fixes.
    Stable items score higher for architectural questions.
    """
    last_modified = item_metadata.get("last_modified")
    if not last_modified:
        return 0.5
    
    days_old = (datetime.utcnow() - last_modified).days
    
    if intent == IntentType.BUG_FIX:
        # Bugs are often in recently changed code
        # Score decays over 30 days
        return max(0.1, 1.0 - (days_old / 30.0))
    else:
        # For architecture questions, older stable code is authoritative
        return min(1.0, 0.5 + (days_old / 180.0))
```

**4. Pattern match (15% weight)**
```python
# gateway/core/ranker/scorers/pattern.py

def score(self, task: str, item_text: str) -> float:
    """
    Direct keyword overlap between task and item.
    Simple but effective for catching exact matches.
    """
    task_words = set(task.lower().split())
    item_words = set(item_text.lower().split())
    
    # Remove stop words
    stop_words = {"the", "a", "an", "is", "in", "to", "for", "of", "with"}
    task_words -= stop_words
    item_words -= stop_words
    
    if not task_words:
        return 0.0
    
    overlap = len(task_words & item_words) / len(task_words)
    return min(1.0, overlap * 2)  # Scale up — partial overlap is still valuable
```

**5. Source authority (10% weight)**
```python
# gateway/core/ranker/scorers/authority.py

AUTHORITY_SCORES = {
    "rip_trace": 0.95,      # Direct call chain — highest authority
    "rip_impact": 0.90,     # Direct dependency data
    "rip_architecture": 0.85,
    "rip_search": 0.75,
    "github_pr": 0.70,      # PR descriptions explain why
    "github_commit": 0.60,
    "jira_ticket": 0.65,
    "slack_message": 0.50,
    "rip_git": 0.55,
}
```

**Weight adjustment by intent:**
```python
INTENT_WEIGHTS = {
    IntentType.BUG_FIX: {
        "semantic": 0.25,
        "centrality": 0.20,
        "recency": 0.35,    # Recency boosted for bugs
        "pattern": 0.10,
        "authority": 0.10,
    },
    IntentType.FEATURE_ADDITION: {
        "semantic": 0.30,
        "centrality": 0.25,
        "recency": 0.20,
        "pattern": 0.15,
        "authority": 0.10,
    },
    IntentType.ARCHITECTURAL_QUESTION: {
        "semantic": 0.35,
        "centrality": 0.30,
        "recency": 0.05,    # Recency irrelevant for understanding architecture
        "pattern": 0.15,
        "authority": 0.15,
    },
    IntentType.REFACTOR: {
        "semantic": 0.25,
        "centrality": 0.35,  # Centrality critical — what depends on what
        "recency": 0.15,
        "pattern": 0.15,
        "authority": 0.10,
    },
}
```

**The compressor — token budget filling:**
```python
# gateway/core/ranker/compressor.py

class ContextCompressor:
    """Fill token budget with highest-scoring items."""
    
    async def compress(
        self,
        scored_items: list[ScoredItem],
        token_budget: int,
        counter: TokenCounter
    ) -> CompressedContext:
        
        # Sort by score descending
        sorted_items = sorted(scored_items, key=lambda x: x.score, reverse=True)
        
        included = []
        excluded = []
        tokens_used = 0
        
        for item in sorted_items:
            item_tokens = counter.count(item.content)
            
            if tokens_used + item_tokens <= token_budget:
                included.append(item)
                tokens_used += item_tokens
            else:
                # Try to fit a summarized version
                summary = await self.summarizer.summarize(
                    item.content,
                    max_tokens=min(300, token_budget - tokens_used)
                )
                if summary and tokens_used + counter.count(summary) <= token_budget:
                    included.append(item.with_content(summary + "\n[truncated]"))
                    tokens_used += counter.count(summary)
                else:
                    excluded.append(item)
        
        return CompressedContext(
            included=included,
            excluded=excluded,
            tokens_used=tokens_used,
            token_budget=token_budget,
            compression_ratio=tokens_used / max(1, sum(
                counter.count(i.content) for i in scored_items
            ))
        )
```

---

### COMPONENT 5 — SESSION MEMORY

**What it does:** Persists every session to PostgreSQL. Detects when multiple sessions are touching the same files simultaneously. Bridges context between related sessions.

**File:** `gateway/core/memory/store.py`

**Session lifecycle:**
```python
class SessionStore:
    
    async def create_session(
        self,
        agent_type: str,
        task: str,
        classification: ClassificationResult
    ) -> Session:
        """Create a new session record when a gateway request starts."""
    
    async def update_files_accessed(
        self,
        session_id: UUID,
        files: list[str]
    ) -> None:
        """Update which files this session touched. Called after execution."""
    
    async def complete_session(
        self,
        session_id: UUID,
        outcome: str,
        files_modified: list[str]
    ) -> None:
        """Mark session complete when agent finishes the task."""
    
    async def get_active_sessions(
        self,
        exclude_session_id: UUID | None = None
    ) -> list[Session]:
        """Get all in-progress sessions. Used for conflict detection."""
    
    async def get_recent_sessions(
        self,
        domain: str,
        hours: int = 24
    ) -> list[Session]:
        """Get sessions from the last N hours for context bridging."""
```

**Conflict detector — the most important memory feature:**
```python
# gateway/core/memory/conflict_detector.py

class ConflictDetector:
    
    async def detect(
        self,
        current_session_id: UUID,
        current_files: list[str]
    ) -> list[Conflict]:
        """
        Find any active session that is touching the same files
        as the current session. Called before delivering context.
        """
        
        active_sessions = await self.store.get_active_sessions(
            exclude_session_id=current_session_id
        )
        
        conflicts = []
        current_file_set = set(current_files)
        
        for session in active_sessions:
            session_files = set(session.files_accessed)
            overlap = current_file_set & session_files
            
            if overlap:
                conflicts.append(Conflict(
                    session_id=session.id,
                    agent_type=session.agent_type,
                    task_description=session.task_description,
                    overlapping_files=list(overlap),
                    started_at=session.started_at,
                    risk_level=self._assess_conflict_risk(overlap, session)
                ))
        
        return conflicts
    
    def _assess_conflict_risk(
        self,
        overlapping_files: set[str],
        other_session: Session
    ) -> str:
        """
        High risk: overlapping files are in payment, auth, or core modules.
        Medium risk: overlapping files are shared utilities.
        Low risk: overlapping test or documentation files.
        """
        high_risk_patterns = ["payment", "auth", "security", "core"]
        for file in overlapping_files:
            if any(pattern in file.lower() for pattern in high_risk_patterns):
                return "high"
        return "medium"
```

**Context bridge — share knowledge between related sessions:**
```python
# gateway/core/memory/context_bridge.py

class ContextBridge:
    """
    When a new session starts on a domain that was recently active,
    pre-load relevant context from the previous session without
    the agent having to ask for it.
    """
    
    async def get_bridged_context(
        self,
        domain: str,
        current_task: str
    ) -> BridgedContext | None:
        
        recent = await self.store.get_recent_sessions(domain, hours=24)
        if not recent:
            return None
        
        most_relevant = self._find_most_relevant(recent, current_task)
        if not most_relevant:
            return None
        
        return BridgedContext(
            from_session_id=most_relevant.id,
            files_previously_accessed=most_relevant.files_accessed,
            task_summary=most_relevant.task_description[:200],
            completed_at=most_relevant.ended_at,
            suggestion=f"Previous session worked on {domain}. Pre-loading context."
        )
```

---

### COMPONENT 6 — RIP MCP CLIENT

**What it does:** Calls RIP's MCP server as a Tier 2 source. Every other source client follows the same pattern.

**File:** `gateway/core/sources/rip_client.py`

```python
class RIPClient:
    """
    Calls RIP MCP server (the one built in Phase 1).
    All calls go through the existing mcp/server.py in the RIP project.
    """
    
    def __init__(self, rip_command: str, rip_args: list[str]):
        self.rip_command = rip_command
        self.rip_args = rip_args
        self._process: asyncio.subprocess.Process | None = None
    
    async def connect(self) -> None:
        """Start the RIP MCP server process."""
        self._process = await asyncio.create_subprocess_exec(
            self.rip_command,
            *self.rip_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        timeout: float = 5.0
    ) -> str:
        """Call a RIP MCP tool and return the text result."""
        
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        request_bytes = (json.dumps(request) + "\n").encode()
        
        try:
            self._process.stdin.write(request_bytes)
            await asyncio.wait_for(
                self._process.stdin.drain(),
                timeout=timeout
            )
            
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=timeout
            )
            
            response = json.loads(response_line.decode())
            content = response.get("result", {}).get("content", [])
            
            return "\n".join(
                block.get("text", "")
                for block in content
                if block.get("type") == "text"
            )
        
        except asyncio.TimeoutError:
            raise TimeoutError(f"RIP tool {tool_name} timed out after {timeout}s")
    
    # Convenience methods matching RIP's tool names
    async def trace(self, symbol: str) -> str:
        return await self.call_tool("rip_trace", {"symbol": symbol})
    
    async def impact(self, symbol: str) -> str:
        return await self.call_tool("rip_impact", {"symbol": symbol})
    
    async def search(self, query: str, top_k: int = 10) -> str:
        return await self.call_tool("rip_search", {"query": query, "top_k": top_k})
    
    async def explain(self, topic: str) -> str:
        return await self.call_tool("rip_explain", {"topic": topic})
    
    async def architecture(self) -> str:
        return await self.call_tool("rip_architecture", {})
    
    async def onboard(self) -> str:
        return await self.call_tool("rip_onboard", {})
```

---

### COMPONENT 7 — THE MCP SERVER (TIER 1)

**What it does:** Exposes the four gateway tools to AI agents via the MCP stdio protocol.

**File:** `gateway/mcp/server.py`

```python
# gateway/mcp/server.py

import asyncio
import json
import sys
from uuid import uuid4
from gateway.mcp.tools import TOOL_DEFINITIONS
from gateway.mcp.handlers import GatewayHandlers

class GatewayMCPServer:
    """
    Tier 1 MCP server. This is what AI agents connect to.
    Exposes 4 clean tools that hide all orchestration complexity.
    """
    
    def __init__(self):
        self.handlers = GatewayHandlers()
    
    async def run(self) -> None:
        """Main stdio loop — reads requests, writes responses."""
        
        while True:
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            if not line:
                break
            
            try:
                request = json.loads(line.strip())
                response = await self._handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(e)}
                }
                print(json.dumps(error_response), flush=True)
    
    async def _handle_request(self, request: dict) -> dict:
        method = request.get("method", "")
        request_id = request.get("id")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "context-gateway",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": TOOL_DEFINITIONS}
            }
        
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            
            result_text = await self.handlers.handle(tool_name, arguments)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
```

**The handlers — orchestration pipeline:**
```python
# gateway/mcp/handlers.py

class GatewayHandlers:
    """
    Connects tool calls to the core pipeline.
    Each tool call goes through the full 6-step pipeline.
    """
    
    async def handle(self, tool_name: str, arguments: dict) -> str:
        
        if tool_name == "get_context":
            return await self._handle_get_context(arguments)
        elif tool_name == "validate_change":
            return await self._handle_validate_change(arguments)
        elif tool_name == "search_codebase":
            return await self._handle_search_codebase(arguments)
        elif tool_name == "explain_architecture":
            return await self._handle_explain_architecture(arguments)
        else:
            return f"Unknown tool: {tool_name}"
    
    async def _handle_get_context(self, args: dict) -> str:
        task = args["task"]
        max_tokens = args.get("max_tokens", 12000)
        role = args.get("role", "developer")
        
        # Step 1: Classify intent
        classification = await self.classifier.classify(task)
        
        # Step 2: Create session
        session = await self.memory.create_session(
            agent_type="unknown",  # Will be enriched by middleware
            task=task,
            classification=classification
        )
        
        # Step 3: Build plan
        plan = await self.planner.build_plan(classification, task, max_tokens)
        
        # Step 4: Execute all queries in parallel
        raw_responses = await self.executor.execute(plan)
        
        # Extract files that will be accessed
        files_accessed = self._extract_files_from_responses(raw_responses)
        await self.memory.update_files_accessed(session.id, files_accessed)
        
        # Step 5: Detect conflicts
        conflicts = await self.conflict_detector.detect(session.id, files_accessed)
        
        # Step 6: Rank and compress
        scored = await self.ranker.score_all(task, classification, raw_responses)
        compressed = await self.compressor.compress(scored, max_tokens)
        
        # Step 7: Filter by permissions
        filtered = await self.permissions.filter(compressed, role)
        
        # Step 8: Assemble final response
        return self._format_response(
            task=task,
            classification=classification,
            compressed=filtered,
            conflicts=conflicts,
            plan=plan,
            session_id=session.id
        )
    
    def _format_response(self, **kwargs) -> str:
        """Format the final markdown response delivered to the agent."""
        classification = kwargs["classification"]
        compressed = kwargs["compressed"]
        conflicts = kwargs["conflicts"]
        session_id = kwargs["session_id"]
        
        sections = []
        
        # Header
        sections.append(
            f"## Context Package\n"
            f"**Intent**: {classification.intent} "
            f"(confidence: {classification.confidence:.0%})\n"
            f"**Domain**: {classification.domain}\n"
            f"**Risk**: {classification.risk_level}\n"
            f"**Session**: {session_id}\n"
        )
        
        # Conflict warnings — show these prominently
        if conflicts:
            sections.append("### ⚠️ Active Conflicts\n")
            for conflict in conflicts:
                sections.append(
                    f"- **{conflict.agent_type}** session is also modifying: "
                    f"{', '.join(conflict.overlapping_files)}\n"
                    f"  Started {conflict.started_at}. "
                    f"Coordinate before making changes.\n"
                )
        
        # Context items grouped by source
        sections.append("### Retrieved Context\n")
        
        by_source = {}
        for item in compressed.included:
            source = item.metadata.get("source", "unknown")
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(item)
        
        for source, items in by_source.items():
            sections.append(f"**{source.upper()}**\n")
            for item in items:
                sections.append(f"{item.content}\n")
        
        # Footer stats
        sections.append(
            f"\n---\n"
            f"*{compressed.tokens_used:,} tokens used of "
            f"{compressed.token_budget:,} budget | "
            f"{len(kwargs['plan'].steps)} sources queried | "
            f"session: {session_id}*\n"
        )
        
        return "\n".join(sections)
```

---

## CONFIGURATION — `gateway/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GATEWAY_",
        case_sensitive=False
    )
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8001
    
    # Database (reuse RIP's PostgreSQL)
    postgres_url: str = "postgresql+asyncpg://rip_user:rip_pass@localhost:5432/rip_db"
    redis_url: str = "redis://localhost:6379/1"  # Different DB from RIP
    
    # RIP MCP server
    rip_mcp_command: str = "uv"
    rip_mcp_args: list[str] = ["run", "python", "mcp/server.py"]
    rip_mcp_cwd: str = "../"  # Path to RIP project
    
    # GitHub MCP (optional)
    github_mcp_enabled: bool = False
    github_token: str = ""
    
    # Jira MCP (optional)
    jira_mcp_enabled: bool = False
    jira_url: str = ""
    jira_token: str = ""
    
    # Slack MCP (optional)
    slack_mcp_enabled: bool = False
    slack_token: str = ""
    
    # LLM for classifier fallback
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5-coder:7b"
    llm_fallback_threshold: float = 0.70
    
    # Token defaults
    default_max_tokens: int = 12000
    min_tokens_per_source: int = 500
    overhead_reserve_ratio: float = 0.10
    
    # Execution
    source_timeout_seconds: float = 5.0
    circuit_breaker_threshold: int = 3
    circuit_breaker_reset_seconds: int = 300
    
    # Cache
    cache_ttl_seconds: int = 300
    
    # Permissions
    default_role: str = "developer"

settings = GatewaySettings()
```

---

## BUILD ORDER — DAY BY DAY

Execute in strict order. Run the verification command at the end of each day before moving forward.

### Day 1 — Skeleton and Config

Create the full directory structure. Create all empty `__init__.py` files. Write `pyproject.toml` with all dependencies. Write `config.py`. Write `.env.example`. Run `uv sync`.

```bash
# Verification
uv run python -c "from gateway.config import settings; print(settings.port)"
# Expected: 8001
```

### Day 2 — Database Schema

Write `gateway/storage/database.py` with async SQLAlchemy session factory. Write `gateway/storage/models.py` with all four ORM models (sessions, session_events, feedback, source_health). Write the Alembic migration `001_initial.py` creating all four tables. Run `alembic upgrade head`.

```bash
# Verification
uv run alembic upgrade head
# Expected: no errors
uv run python -c "
import asyncio
from gateway.storage.database import get_session
asyncio.run(async_test())
"
```

### Day 3 — Intent Classifier

Write `patterns.py` with keyword lists for all intent types and domains. Write `rules.py` with regex-based classification logic. Write `models.py` with `ClassificationResult`. Write `engine.py` that tries rules first, returns result. Do not write `few_shot.py` yet — that is a Day 5 addition.

```bash
# Verification
uv run pytest tests/unit/test_classifier.py -v
# All four test cases must pass
```

### Day 4 — Multi-Source Planner

Write `models.py` with `Plan`, `RetrievalStep`, `SourceQuery`. Write `strategies.py` with the complete strategy table for all six intent types. Write `budget.py` with token allocation logic. Write `engine.py` that builds a plan from a classification result.

```bash
# Verification
uv run pytest tests/unit/test_planner.py -v
# Plan for bug_fix must have RIP trace in priority 1
# Plan for architectural_question must include Slack
```

### Day 5 — RIP Client and Source Registry

Write `gateway/core/sources/base.py` with base MCP client interface. Write `rip_client.py` that connects to and calls the RIP MCP server process. Write `registry.py` that tracks available sources and their health. Test the RIP client against the running RIP MCP server.

```bash
# Verification — RIP must be running
uv run python -c "
import asyncio
from gateway.core.sources.rip_client import RIPClient

async def test():
    client = RIPClient('uv', ['run', 'python', 'mcp/server.py'])
    await client.connect()
    result = await client.search('parser')
    print(result[:200])
    
asyncio.run(test())
"
# Expected: search results from RIP
```

### Day 6 — Parallel Executor

Write `models.py` with `SourceResponse`. Write `circuit_breaker.py`. Write `retry.py` with exponential backoff. Write `engine.py` with `asyncio.gather` parallel execution.

```bash
# Verification
uv run pytest tests/unit/test_executor.py -v
uv run pytest tests/performance/test_parallel_execution.py -v
# Parallel execution must be faster than sequential
```

### Day 7 — Token Counter

Write `gateway/core/tokenizer/counter.py` using tiktoken. Write `budget.py` with allocation logic. Write `models.py`.

```bash
# Verification
uv run python -c "
from gateway.core.tokenizer.counter import TokenCounter
counter = TokenCounter()
print(counter.count('Hello world'))  # Expected: ~3
print(counter.count('def authenticate_user(email: str, password: str) -> User:'))  # ~15
"
```

### Day 8 — Ranker Scorers

Write all five scorer files in `scorers/`. Write `models.py` with `ScoredItem`. Write `engine.py` that runs all five scorers and produces a weighted final score.

```bash
# Verification
uv run pytest tests/unit/test_ranker.py -v
# Higher-relevance items must score higher than lower-relevance items
```

### Day 9 — Compressor and Deduplicator

Write `deduplicator.py` that removes near-duplicate items. Write `compressor.py` that fills token budget with top-scored items. Write `summarizer.py` that creates brief summaries for overflow items.

```bash
# Verification
uv run pytest tests/unit/test_compressor.py -v
# Total tokens in output must never exceed budget
# Highest-scoring items must always be included first
```

### Day 10 — Session Memory

Write `models.py` with Session, SessionEvent, Conflict, BridgedContext. Write `store.py` with CRUD operations against PostgreSQL. Write `conflict_detector.py`. Write `context_bridge.py`.

```bash
# Verification
uv run pytest tests/unit/test_memory.py -v
uv run pytest tests/integration/test_conflict_detection.py -v
# Two sessions touching the same files must produce a conflict
```

### Day 11 — Permission System

Write `roles.py` with role definitions. Write `policies.py` with access rules. Write `engine.py` that filters context by role. Write `audit.py` that logs every access decision.

```bash
# Verification
uv run pytest tests/unit/test_permissions.py -v
# Junior dev must not receive production log content
# Senior dev must receive everything
```

### Day 12 — MCP Tier 1 Server

Write `gateway/mcp/tools.py` with all four tool definitions. Write `gateway/mcp/handlers.py` that wires tools to the core pipeline. Write `gateway/mcp/server.py` with the stdio MCP server loop.

```bash
# Verification — test MCP protocol directly
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | \
  uv run python -m gateway.mcp.server
# Expected: JSON response listing all 4 tools
```

### Day 13 — End-to-End Integration

Wire everything together. The `get_context` handler must call classifier → session create → planner → executor (RIP queries only) → conflict detector → ranker → compressor → permissions → format response.

```bash
# Verification — the most important test
uv run pytest tests/integration/test_full_pipeline.py -v

# Manual test
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_context","arguments":{"task":"Add retry logic to payment service","max_tokens":8000}}}' | \
  uv run python -m gateway.mcp.server
# Expected: Structured context package with payment-related RIP results
```

### Day 14 — FastAPI HTTP Server

Write `gateway/server/app.py`. Write all routers. Write middleware (auth, rate limiting, logging). Write request/response schemas.

```bash
# Verification
uv run uvicorn gateway.server.app:app --port 8001
curl http://localhost:8001/health
# Expected: {"status": "healthy", "sources": {...}}
```

### Day 15 — External Sources (GitHub)

Write `github_client.py` that calls GitHub MCP for open PRs, recent commits, and similar PRs. Wire it into the executor. Test it with a real GitHub repository.

```bash
# Verification — requires GITHUB_TOKEN in .env
uv run pytest tests/integration/test_full_pipeline.py -v -k "github"
```

### Day 16 — Jira and Slack Clients

Write `jira_client.py` and `slack_client.py` following the same pattern as github_client.py. Both are optional — the gateway must work correctly when they are unavailable.

### Day 17 — CLI

Write `gateway/cli/main.py` Typer app. Write `start.py` (launch gateway), `status.py` (show health), `sources.py` (list/enable/disable sources), `mcp.py` (generate agent config).

```bash
# Verification
gateway start          # Starts the gateway
gateway status         # Shows health and active sessions
gateway sources list   # Shows all configured sources
gateway mcp config     # Prints JSON to add to Claude Code settings
```

### Day 18 — Learning Loop

Write `gateway/core/memory/learning.py`. Implement the feedback loop where poor-quality sessions (low rating or missing context reports) adjust scorer weights for future similar tasks.

### Day 19 — LLM Classifier Fallback

Write `few_shot.py` that calls the LLM with few-shot examples when rule-based classification confidence is below 0.70. This handles ambiguous cases like "clean up the auth code" which could be refactor or bug fix depending on context.

### Day 20 — Full Test Suite and Documentation

Run the complete test suite. Fix every failure. Write `docs/setup.md` with a 5-step getting-started guide. Write `docs/mcp.md` explaining how to connect Claude Code, Cursor, and Codex.

---

## AGENT CONFIGURATION — HOW TO CONNECT CLAUDE CODE

After building, this is what users add to their Claude Code config:

```json
{
  "mcpServers": {
    "context-gateway": {
      "command": "gateway",
      "args": ["mcp-server"],
      "env": {
        "GATEWAY_RIP_MCP_CWD": "/path/to/rip/project"
      }
    }
  }
}
```

The `gateway mcp config` CLI command generates this automatically for every supported agent.

---

## SUCCESS CRITERIA — ALL MUST PASS

```bash
# 1. All tests green
uv run pytest tests/ -v
# Expected: 0 failures

# 2. Linter clean
uv run ruff check .
# Expected: no errors

# 3. Single tool call produces complete context
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_context","arguments":{"task":"Fix the authentication bug in login flow"}}}' | \
  uv run python -m gateway.mcp.server
# Expected: structured context with auth-related code, recent commits, conflict check

# 4. Parallel execution is faster than sequential
uv run pytest tests/performance/test_parallel_execution.py -v
# Expected: parallel < 2x single source time

# 5. Token budget never exceeded
uv run pytest tests/integration/test_full_pipeline.py -v -k "budget"
# Expected: all responses within token budget

# 6. Conflict detection works
uv run pytest tests/integration/test_conflict_detection.py -v
# Expected: overlapping sessions trigger warnings

# 7. Circuit breaker prevents cascading failures
uv run pytest tests/unit/test_executor.py -v -k "circuit"
# Expected: failed source does not block other sources

# 8. Gateway health endpoint responds
curl http://localhost:8001/health
# Expected: {"status": "healthy"}
```

---

## WHAT NOT TO BUILD IN THIS PHASE

Skip these. They are valuable but not required for a working gateway.

- Prometheus/Grafana monitoring — add later
- Multi-instance load balancing — single instance is sufficient
- Kubernetes deployment manifests — Docker Compose is enough
- Advanced learning algorithms — simple weight adjustment is sufficient
- Mobile or web dashboard — CLI is sufficient
- RBAC admin UI — config file is sufficient

---

## REUSE FROM RIP — DO NOT REBUILD

These components already exist in the RIP project and should be imported or copied rather than rebuilt.

- `sentence_transformers` model loading — reuse the embedding pipeline from `core/search/embedder.py`
- LiteLLM client pattern — reuse from `core/llm/client.py`
- Rich terminal formatting patterns — reuse from `cli/output/formatters.py`
- Pydantic settings pattern — reuse from `server/config.py`
- Async SQLAlchemy session factory — reuse from `core/storage/database.py`
- MCP stdio server pattern — extend `mcp/server.py` rather than rewriting

The gateway is built on top of RIP, not parallel to it. Every hour spent rewriting something that already works in RIP is wasted.
