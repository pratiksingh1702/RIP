# Context Gateway API Flow Documentation
## Overview
The Context Gateway is a smart orchestration layer that sits on top of the Repository Intelligence Platform (RIP) and other data sources. It processes coding task requests, classifies intent, plans and retrieves data from multiple sources, and returns relevant, compressed context for AI agents.

---

## Complete Endpoint Flow: `POST /api/context`
This is the primary endpoint for retrieving task context.

### Request Schema
```json
{
  "task": "string",
  "max_tokens": 12000,
  "role": "developer"
}
```
- `task`: The coding task description
- `max_tokens`: Maximum tokens in response context
- `role`: User role for permissions

### Response Schema
```json
{
  "session_id": "string",
  "intent": "string",
  "domain": "string",
  "context": [
    {
      "source": "string",
      "query_type": "string",
      "content": "string",
      "metadata": {},
      "score": 0.0
    }
  ],
  "tokens_used": 0,
  "conflicts": [{}],
  "warnings": []
}
```

---

## Step-by-Step Pipeline Execution
**Orchestration File**: `gateway/gateway/core/pipeline.py`

### Step 1: Intent Classification
- **File**: `gateway/gateway/core/classifier/engine.py`
- **Component**: `ClassifierEngine`
- **Process**:
  1. Uses rule-based classification (`classify_intent()` from rules.py)
  2. Domain detection (`detect_domain()` from rules.py)
  3. Risk assessment (`assess_risk()` from rules.py)
  4. If confidence < `llm_fallback_threshold` and `llm_fallback_enabled`, use LLM fallback
  5. Returns `ClassificationResult`: intent, domain, risk, confidence, strategy

### Step 2: Session Creation
- **File**: `gateway/gateway/core/memory/store.py`
- **Component**: `SessionStore`
- **Process**:
  1. Store task and classification in PostgreSQL
  2. Return session ID for tracking
  3. Updates later for conflict detection with existing sessions

### Step 3: Query Planning
- **File**: `gateway/gateway/core/planner/engine.py`
- **Component**: `PlannerEngine`
- **Process**:
  1. Get strategy from `STRATEGY_TABLE` based on intent (strategies.py)
  2. Build `always_query` queries
  3. Add conditional queries if source is enabled and conditions match
  4. Allocate token budget to sources
  5. Return Plan with retrieval steps (all steps are parallel)

### Step 4: Parallel Execution
- **File**: `gateway/gateway/core/executor/engine.py`
- **Component**: `ExecutorEngine`
- **Process**:
  1. Iterate over retrieval steps
  2. Parallel execute all queries in step simultaneously:
    ```python
    tasks = [self._execute_single_query(query) for query in step.queries]
    asyncio.gather(*tasks, return_exceptions=True)
    ```
  3. Individual query circuit breaker - if a source fails too many times, skip it
  4. Track success/failure counts & latencies
  5. Extract files accessed from all responses
  6. Update session with accessed files
  7. Return `ExecutorResult`: list(SourceResponse)

### Step 4a: RIPSource Query Execution
- **File**: `gateway/gateway/core/sources/rip_client.py`
- **Component**: `RIPSource`
- **Actual RIP CLI Commands Executed**:
  - `uv run repo search <target> --limit 10` (for query_type="search")
  - `uv run repo architecture` (for query_type="architecture")
  - `uv run repo trace <target>` (for query_type="trace")
  - `uv run repo impact <target>` (for query_type="impact")
- **Process**:
  1. In `_cli_query()` function, build args based on query type
  2. Run async subprocess with RIP CLI commands
  3. Capture stdout/stderr
  4. Return stdout as response
  5. Use `_extract_file_paths()` to extract file paths from RIP output!

### Step 5: Conflict Detection
- **File**: `gateway/gateway/core/memory/conflict_detector.py`
- **Component**: `ConflictDetector`
- **Process**:
  - Check other active sessions
  - Find if they are accessing same files
  - Return conflicts with session_ids & risk_level

### Step 6: Ranking and Compression
- **File**: `gateway/gateway/core/ranker/engine.py`
- **Component**: `RankerEngine`
- **Process**:
  1. Score items using multiple scorers (semantic, recency, pattern, authority, centrality)
  2. Deduplicate items
  3. Compress to stay within token budget
  4. Rank from highest to lowest
  5. Return most important items first

### Step 7: Permission Filtering
- **File**: `gateway/gateway/core/permissions/engine.py`
- **Component**: `PermissionEngine`
- **Process**:
  - Filter context items based on user role & domain
  - Returns only permitted items

---

## Other Endpoints

### 1. Health Check
- `GET /health`
- **Response**: Status, version, source availability
- **File**: `gateway/gateway/server/routers/health.py`

### 2. Sources
- `GET /api/sources` → List available/enabled sources
- `POST /api/sources/{name}/enable` → Enable a source
- `POST /api/sources/{name}/disable` → Disable a source
- **File**: `gateway/gateway/server/routers/sources.py`

### 3. Sessions
- `GET /api/sessions` → List all active sessions
- `GET /api/sessions/{session_id}` → Get details of a specific session
- **File**: `gateway/gateway/server/routers/sessions.py`

### 4. Metrics
- `GET /api/metrics` → Gateway stats
- **File**: `gateway/gateway/server/routers/metrics.py`

### 5. Validate
- `POST /api/validate` → Validate code changes
- **File**: `gateway/gateway/server/routers/validate.py`

---
