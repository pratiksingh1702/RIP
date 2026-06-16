# RIP Architecture Audit and Reliability Review

You are auditing Repository Intelligence Platform (RIP).

IMPORTANT RULES:

1. DO NOT edit files immediately.
2. First inspect and understand the implementation.
3. Find bugs, suspicious logic, architectural weaknesses, and performance issues.
4. Only after proving the root cause should you suggest code changes.

---

# Current Project Status

Implemented:

* Neo4j graph database
* Qdrant vector database
* Python parser
* TypeScript parser
* Java parser
* Go parser
* Rust parser
* Incremental indexing
* Watch mode
* Embedding pipeline
* Semantic search
* Hybrid search
* Impact analysis
* Trace engine
* Explain engine
* FastAPI server
* Persistent runtime
* MCP server
* VSCode extension

Current graph:

Nodes: ~1200+

Relationships: ~2800+

Relationship types:

* CALLS
* IMPORTS
* DEPENDS_ON
* EXTENDS
* CONTAINS
* REPRESENTS

Qdrant:

* points_count ≈ 319
* embeddings generated ≈ 319

---

# Suspicion 1

File:

core/search/indexer.py

Function:

index_entities_batched()

Observed:

for start in range(0, len(entities), batch_size):
batch = entities

This looks suspicious.

Check:

Should it be:

batch = entities[start:start+batch_size]

Questions:

* Are embeddings duplicated?
* Is memory wasted?
* Is batching fake?
* Is indexing slower than expected?

---

# Suspicion 2

File:

core/indexer/incremental.py

Observed:

for filepath in all_files:
current_hashes = file_hash

Questions:

Should it be:

current_hashes[rel_path] = file_hash

Verify:

* Are hashes stored correctly?
* Is incremental indexing actually working?
* Are unchanged files unnecessarily reindexed?

---

# Suspicion 3

Explain command

Command:

repo explain "How indexing works"

Output:

LLM not available, showing raw context.

Investigate:

* Why LiteLLM fails
* Missing API key?
* Bad provider?
* Bad model?
* Timeout?
* Error swallowed?

Check:

core/llm/client.py

server/config.py

core/llm/prompts/

---

# Suspicion 4

Search flow

Verify complete flow:

User query

↓

Embedding

↓

Qdrant semantic search

↓

Neo4j enrichment

↓

Results

Check:

core/search/searcher.py

Questions:

* Does search always use Qdrant?
* Is there fallback to Neo4j?
* Can stale graph data return incorrect results?

---

# Suspicion 5

Persistent runtime

Files:

server/runtime.py

server/app.py

Check:

* Is embedder singleton?
* Is reranker singleton?
* Is model loaded more than once?
* Why does:

Loading weights

appear multiple times?

---

# Suspicion 6

Qdrant lifecycle

Inspect:

core/search/client.py

Questions:

* Can collection be recreated accidentally?
* Are deletes too aggressive?
* Can inserts be lost?
* Are counters trustworthy?

---

# Suspicion 7

Trace engine

Test:

repo trace PythonParser

repo trace BaseParser

repo trace Searcher

repo trace hybrid_search

Verify:

* Classes
* Functions
* Methods
* Imports
* Inheritance
* Nested relationships

Find missing edge cases.

---

# Suspicion 8

Architecture generation

Command:

repo architecture

Verify:

* Mermaid output quality
* Missing nodes
* Missing relationship types
* Cycles
* Duplicate edges

---

# Suspicion 9

MCP server

Inspect:

mcp/server.py

Questions:

* Which tools are exposed?
* Is stdio protocol compliant?
* Can Codex call:

search

trace

impact

explain

architecture

metrics

---

# Deliverables

DO NOT EDIT FIRST.

Return:

1. Critical bugs
2. Hidden bugs
3. Architectural concerns
4. Performance bottlenecks
5. Memory problems
6. Code smells
7. Production risks
8. Security risks
9. Reliability concerns
10. Suggestions ranked by priority

For every concern:

* file
* line
* evidence
* impact
* fix

Evidence first.

Code second.
