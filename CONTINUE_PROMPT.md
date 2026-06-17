# Task: Implement Repository Isolation Across Neo4j, Qdrant, and Future Storage Layers

## Goal

Refactor the Repository Intelligence Platform (RIP) so that every indexed repository is fully isolated and queryable independently.

Currently, entities from multiple repositories may coexist in the same Neo4j graph and Qdrant collection without strict ownership boundaries.

This is unacceptable for production use.

The system must guarantee that:

* Searches never leak entities across repositories.
* Graph traversals remain repository-scoped.
* Embeddings are repository-scoped.
* Future multi-repository features can explicitly connect repositories rather than accidentally mixing them.

---

# Requirements

## 1. Introduce Project Model

Create a Project entity.

Fields:

```typescript
interface Project {
    id: string;
    name: string;
    root: string;
    language: string;
    createdAt: Date;
}
```

Store projects in PostgreSQL (or existing metadata layer).

---

## 2. Neo4j Isolation

Create project ownership nodes.

Graph model:

```text
(Project)-[:CONTAINS]->(File)

(Project)-[:OWNS]->(Class)

(Project)-[:OWNS]->(Function)

(Project)-[:OWNS]->(Module)

(Project)-[:OWNS]->(API)
```

Every entity node must contain:

```text
project_id
```

Every graph query must filter by:

```cypher
WHERE entity.project_id = $projectId
```

or traverse from:

```cypher
MATCH (p:Project {id:$projectId})
```

No query may operate globally unless explicitly requested.

---

## 3. Qdrant Isolation

Choose one of these approaches:

Preferred:

```json
{
  "project_id": "uuid",
  "project_name": "flutter_app",
  "entity_type": "function"
}
```

and apply payload filtering on every search.

Example:

```python
Filter(
    must=[
        FieldCondition(
            key="project_id",
            match=MatchValue(value=project_id)
        )
    ]
)
```

Alternative:

Separate collections:

```text
flutter_entities
spring_entities
nestjs_entities
```

Document tradeoffs and recommend one.

---

## 4. Indexing Pipeline

When indexing:

```text
Repository
 ↓
Create Project
 ↓
Parse Files
 ↓
Generate Entities
 ↓
Attach project_id
 ↓
Store Neo4j
 ↓
Store Qdrant
```

Every indexed object must contain:

```text
project_id
```

No exceptions.

---

## 5. CLI Changes

Add:

```bash
repo projects
```

Returns:

```text
ID      Name
------------------
p1      rip
p2      flutter-app
p3      spring-api
```

Add:

```bash
repo use p1
```

Stores active project.

Subsequent commands:

```bash
repo explain UserService
repo search auth
repo graph
```

must operate against active project.

Allow override:

```bash
repo explain UserService --project p2
```

---

## 6. Validation Tests

Create tests proving isolation.

Example:

Repository A:

```text
AuthService
```

Repository B:

```text
AuthService
```

Query:

```bash
repo explain AuthService --project A
```

must never return data from project B.

Create integration tests for:

* Neo4j queries
* Qdrant retrieval
* Hybrid search
* Graph expansion

---

## Deliverables

1. Updated schema
2. Migration plan
3. Code changes
4. Isolation tests
5. Architecture documentation

Success criteria:

No repository entity can appear in results unless it belongs to the selected project.
# Task: Implement Production-Grade Hybrid Retrieval Pipeline

## Goal

Improve repository question-answering accuracy significantly.

Current pipeline:

```text
Question
 ↓
Embedding
 ↓
Qdrant
 ↓
Top K
 ↓
LLM
```

This produces missed references, poor ranking, and hallucinations.

Replace it with a hybrid retrieval architecture.

---

# Target Architecture

```text
Question
 ↓

BM25 Search
 +
Vector Search
 +
Neo4j Graph Expansion

 ↓

Candidate Pool

 ↓

Cross Encoder Reranker

 ↓

Top Context

 ↓

Context Compression

 ↓

LLM
```

---

# Phase 1: BM25 Retrieval

Implement lexical retrieval.

Options:

* Tantivy
* Elasticsearch
* OpenSearch
* Meilisearch

Index:

```text
Function names
Class names
File names
Comments
Documentation
API descriptions
```

Retrieve:

```text
Top 30 BM25
```

---

# Phase 2: Vector Retrieval

Keep Qdrant.

Retrieve:

```text
Top 30 Semantic Matches
```

Payload filter:

```json
{
  "project_id": "<active-project>"
}
```

Required.

---

# Phase 3: Neo4j Expansion

For retrieved entities:

Expand graph neighbors.

Example:

```text
AuthService
```

Expand:

```text
calls
imports
inherits
implements
used_by
references
```

Depth:

```text
1-2 hops
```

Limit explosion.

---

# Phase 4: Candidate Merge

Merge:

```text
BM25
+
Qdrant
+
Graph Neighbors
```

Deduplicate.

Generate candidate pool:

```text
50-100 entities
```

---

# Phase 5: Cross Encoder Reranker

Add reranker.

Recommended:

```text
bge-reranker-large
```

or

```text
ms-marco cross encoder
```

Input:

```text
(question, candidate)
```

Output:

```text
relevance score
```

Keep:

```text
Top 10-20
```

---

# Phase 6: Context Compression

Current issue:

```text
20 entities
 ↓
20k tokens
 ↓
hallucination
```

Instead:

Create repository-aware summaries.

Per entity:

```text
Name
Purpose
Inputs
Outputs
Dependencies
Related Components
```

Compress before prompt construction.

Target:

```text
3000-5000 tokens
```

Maximum:

```text
6000 tokens
```

---

# Phase 7: Prompt Construction

Context format:

```text
Repository Summary

Relevant Components

Dependency Relationships

Execution Flow

Code Snippets
```

Avoid dumping raw files.

Prefer structured context.

---

# Metrics

Measure:

## Retrieval Recall

Questions:

```text
How login works
Where payment is processed
What breaks if AuthService changes
```

Target:

```text
Recall@20 > 90%
```

---

## Reranker Gain

Measure:

```text
Before reranker
After reranker
```

Expected improvement:

```text
15-30%
```

---

## Hallucination Reduction

Track:

```text
Unsupported statements
```

Target:

```text
50% reduction
```

---

## Latency

Target:

```text
Retrieval < 500ms

Rerank < 500ms

Prompt Build < 200ms
```

Total:

```text
< 2 seconds
```

---

# Deliverables

1. BM25 implementation
2. Hybrid retrieval layer
3. Graph expansion engine
4. Cross encoder reranker
5. Context compression module
6. Benchmark suite
7. Accuracy report

Success criteria:

Repository Q&A consistently outperforms pure vector search on architecture, dependency, and impact-analysis questions.