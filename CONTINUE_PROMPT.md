# RIP — Agent Continuation Prompt
## Pick Up From Current State and Complete the Intelligence Layer

---

## READ THIS FIRST — YOUR CURRENT SITUATION

You are continuing development of the Repository Intelligence Platform (RIP). Do not start from scratch. Do not re-read the full architecture spec unless you need a specific detail. The project structure already exists and is working.

Here is exactly where things stand right now:

### What is fully working
- `repo init` — creates config correctly
- `repo index` — parses files, extracts entities, generates embeddings, stores in Qdrant
- `repo search` — semantic search works, returns relevant results
- `repo impact` — reads graph relationships, returns affected files and risk level
- `repo onboard` — generates onboarding report
- All Docker services running: Neo4j, PostgreSQL, Redis, Qdrant
- 122 files indexed, 278 entities stored

### What is broken and why
- `repo trace` — returns "No trace found" because the Cypher query only searches `(start:Function)` but `PythonParser`, `TypeScriptParser` etc are `Class` nodes. Query mismatch.
- `repo explain` — returns "Symbol not found" because the graph lookup before LLM call is failing
- `repo architecture` — outputs empty `graph TD` because EXTENDS and IMPLEMENTS relationships are not being created during indexing
- `repo metrics` — returns all zeros because git intelligence is not populated
- `repo dead-code` — unreliable because CALLS relationships are incomplete

### What is missing from the graph
The indexing pipeline creates these relationships:
- CONTAINS ✅
- CALLS ✅ (partial)
- IMPORTS ✅ (partial)

But does NOT create:
- DEPENDS_ON ❌
- EXTENDS ❌
- IMPLEMENTS ❌
- MODIFIES ❌ (git)
- OWNED_BY ❌ (git)
- AUTHORED ❌ (git)

### Known technical issues to fix
- Qdrant client version 1.18.0 vs server version 1.10.1 — mismatch, needs alignment
- BGE-M3 embedding model is 2GB+ — needs migration to smaller model
- Trace Cypher query hardcoded to Function nodes only — needs to support Class and Module nodes

---

## YOUR TASK ORDER

Work through these fixes in strict order. Complete each one fully before moving to the next. After each fix, run the verification command listed. Do not skip verifications.

---

## Fix 1 — Repair the Trace Engine

**File to fix:** `core/graph/queries/trace.py`

**The problem:** The current Cypher query is:
```cypher
MATCH path = (start:Function {name: $entry_point})-[:CALLS*1..10]->(end:Function)
RETURN path ORDER BY length(path) DESC LIMIT 50
```

This only finds Function nodes. When the user types `repo trace PythonParser` it fails because PythonParser is a Class node.

**What to build:** Replace the single query with a multi-strategy approach that tries all node types:

```python
# core/graph/queries/trace.py

TRACE_QUERIES = [
    # Strategy 1: Function calling functions
    """
    MATCH path = (start:Function {name: $symbol})-[:CALLS*1..10]->(end)
    RETURN path, 'function_calls' as strategy
    ORDER BY length(path) DESC LIMIT 30
    """,
    
    # Strategy 2: Class containing functions that call things
    """
    MATCH (cls:Class {name: $symbol})-[:CONTAINS]->(method:Function)
    MATCH path = (method)-[:CALLS*1..8]->(end)
    RETURN path, 'class_methods' as strategy
    ORDER BY length(path) DESC LIMIT 30
    """,
    
    # Strategy 3: Module imports
    """
    MATCH path = (start {name: $symbol})-[:IMPORTS|DEPENDS_ON*1..5]->(end)
    RETURN path, 'imports' as strategy
    ORDER BY length(path) DESC LIMIT 20
    """,
    
    # Strategy 4: Fuzzy name match (partial name)
    """
    MATCH (n) WHERE toLower(n.name) CONTAINS toLower($symbol)
    MATCH path = (n)-[:CALLS|IMPORTS|CONTAINS*1..6]->(end)
    RETURN path, 'fuzzy' as strategy
    ORDER BY length(path) DESC LIMIT 20
    """
]

async def trace_symbol(client, symbol: str) -> dict:
    results = []
    strategy_used = None
    
    for query in TRACE_QUERIES:
        async with client.session() as session:
            result = await session.run(query, symbol=symbol)
            records = await result.data()
            if records:
                results = records
                strategy_used = records[0].get('strategy', 'unknown')
                break
    
    if not results:
        # Last resort: find the node and show its immediate connections
        fallback = """
        MATCH (n) WHERE toLower(n.name) CONTAINS toLower($symbol)
        OPTIONAL MATCH (n)-[r]->(connected)
        RETURN n, r, connected LIMIT 20
        """
        async with client.session() as session:
            result = await session.run(fallback, symbol=symbol)
            records = await result.data()
            return {
                "found": len(records) > 0,
                "symbol": symbol,
                "strategy": "immediate_connections",
                "hops": records,
                "message": f"Showing immediate connections for '{symbol}'"
            }
    
    return {
        "found": True,
        "symbol": symbol,
        "strategy": strategy_used,
        "hops": results
    }
```

**Verification after fix:**
```bash
uv run repo trace PythonParser
uv run repo trace BaseParser
uv run repo trace parse_file
```

At least two of these three should return a non-empty trace. If the third returns empty, that is acceptable — it means that specific symbol has no outgoing connections, which is valid.

---

## Fix 2 — Complete the Relationship Extraction in the Graph Builder

**File to fix:** `core/graph/builder.py`

**The problem:** The graph builder creates nodes but is not creating all the relationships that queries depend on. Specifically EXTENDS, IMPLEMENTS, and DEPENDS_ON are missing.

**What to build:** Add relationship creation for every relationship type the queries expect. Go through the builder and verify each of these is being written to Neo4j:

### CALLS relationship
When function A calls function B:
```cypher
MATCH (a:Function {fqn: $from_fqn}), (b:Function {name: $to_name})
MERGE (a)-[:CALLS]->(b)
```

### IMPORTS relationship  
When file A imports module B:
```cypher
MATCH (a:File {path: $file_path})
MERGE (b:Module {name: $module_name})
MERGE (a)-[:IMPORTS]->(b)
```

### EXTENDS relationship
When class A extends class B (inheritance):
```cypher
MATCH (a:Class {fqn: $child_fqn})
MERGE (b:Class {name: $parent_name})
MERGE (a)-[:EXTENDS]->(b)
```

This comes from the Python parser when it finds `class MyParser(BaseParser):` — the `BaseParser` is the parent.

### IMPLEMENTS relationship
When class A implements interface B:
```cypher
MATCH (a:Class {fqn: $class_fqn})
MERGE (b:Interface {name: $interface_name})
MERGE (a)-[:IMPLEMENTS]->(b)
```

### DEPENDS_ON relationship
Module level dependency when a file imports another file in the same project:
```cypher
MATCH (a:Module {name: $from_module})
MERGE (b:Module {name: $to_module})
MERGE (a)-[:DEPENDS_ON]->(b)
```

### CONTAINS relationship
File contains class, class contains function:
```cypher
MATCH (f:File {path: $file_path}), (c:Class {fqn: $class_fqn})
MERGE (f)-[:CONTAINS]->(c)

MATCH (c:Class {fqn: $class_fqn}), (fn:Function {fqn: $function_fqn})
MERGE (c)-[:CONTAINS]->(fn)
```

**After updating the builder, verify by checking Neo4j directly:**
```bash
# Open Neo4j browser at http://localhost:7474
# Login with neo4j / password (or whatever your config says)
# Run these queries in the browser:

MATCH ()-[r:EXTENDS]->() RETURN count(r) as extends_count
MATCH ()-[r:IMPLEMENTS]->() RETURN count(r) as implements_count
MATCH ()-[r:CALLS]->() RETURN count(r) as calls_count
MATCH ()-[r:IMPORTS]->() RETURN count(r) as imports_count
MATCH ()-[r:DEPENDS_ON]->() RETURN count(r) as depends_count
MATCH ()-[r:CONTAINS]->() RETURN count(r) as contains_count
```

All counts should be greater than zero after re-indexing.

**Then re-index and re-verify:**
```bash
uv run repo index .
# Wait for completion
uv run repo trace PythonParser
uv run repo architecture
```

---

## Fix 3 — Fix the Python Parser to Extract Inheritance

**File to fix:** `core/parser/languages/python.py`

**The problem:** The parser extracts classes but is not extracting their base classes (inheritance). When it sees `class PythonParser(BaseParser):` it stores `PythonParser` as a class but does not record that it extends `BaseParser`.

**What to add:** In the Python parser, when extracting a class definition, also extract the base classes list from the AST and store them as `ParsedRelationship` objects with type `EXTENDS`.

Using Tree-sitter, the class definition node has a child called `argument_list` or `bases` that contains the parent class names.

```python
# In python.py, inside the class extraction method

def _extract_class_bases(self, class_node, source_code: bytes) -> List[str]:
    """Extract base class names from a class definition."""
    bases = []
    
    # Tree-sitter node type for base classes in Python is 'argument_list'
    # inside the class definition
    for child in class_node.children:
        if child.type == 'argument_list':
            for base in child.children:
                if base.type == 'identifier':
                    bases.append(base.text.decode('utf-8'))
                elif base.type == 'attribute':
                    # Handles module.ClassName style inheritance
                    bases.append(base.text.decode('utf-8'))
    
    return bases

# Then in your main extraction loop, when you create a ParsedEntity for a class:
base_classes = self._extract_class_bases(class_node, source_bytes)
for base in base_classes:
    relationships.append(ParsedRelationship(
        from_fqn=class_fqn,
        to_fqn=base,  # Will be resolved to full FQN later if possible
        relationship_type="EXTENDS",
        file_path=str(file_path),
        line=class_node.start_point[0]
    ))
```

**Verification:**
```bash
uv run python -c "
from core.parser.languages.python import PythonParser
from pathlib import Path
parser = PythonParser()
content = '''
class BaseParser:
    pass

class PythonParser(BaseParser):
    def parse(self):
        pass
'''
result = parser.parse_file(Path('test.py'), content)
rels = [r for r in result.relationships if r.relationship_type == 'EXTENDS']
print(f'Found {len(rels)} EXTENDS relationships')
for r in rels:
    print(f'  {r.from_fqn} EXTENDS {r.to_fqn}')
"
```

Expected output:
```
Found 1 EXTENDS relationships
  PythonParser EXTENDS BaseParser
```

---

## Fix 4 — Fix the Explain Command

**File to fix:** `core/llm/context_assembler.py` and `cli/commands/explain.py`

**The problem:** `repo explain parser` fails because the graph lookup cannot find a node named exactly "parser". The lookup is too strict — it requires an exact name match.

**What to build:** Make the explain command use semantic search first, then graph enrichment, rather than requiring an exact graph node match.

```python
# core/llm/context_assembler.py

async def assemble_explain_context(
    self,
    topic: str,
    graph_client,
    search_client,
    max_tokens: int = 6000
) -> str:
    
    # Step 1: Semantic search to find relevant entities
    search_results = await search_client.search(topic, top_k=10)
    
    if not search_results:
        return f"No relevant code found for topic: {topic}"
    
    # Step 2: Get graph context for the top results
    graph_context = []
    for result in search_results[:5]:
        entity_name = result.get('name') or result.get('entity_name', '')
        if entity_name:
            # Get what this entity connects to
            query = """
            MATCH (n {name: $name})
            OPTIONAL MATCH (n)-[r]->(connected)
            OPTIONAL MATCH (caller)-[r2]->(n)
            RETURN n, 
                   collect(distinct {rel: type(r), target: connected.name}) as outgoing,
                   collect(distinct {rel: type(r2), source: caller.name}) as incoming
            LIMIT 1
            """
            async with graph_client.session() as session:
                result_data = await session.run(query, name=entity_name)
                records = await result_data.data()
                if records:
                    graph_context.append(records[0])
    
    # Step 3: Build context package
    sections = []
    sections.append(f"Topic: {topic}\n")
    sections.append("## Relevant Code Entities\n")
    
    for i, result in enumerate(search_results[:8]):
        name = result.get('name', result.get('entity_name', 'unknown'))
        file_path = result.get('file_path', '')
        code = result.get('raw_code', result.get('content', ''))[:500]
        sections.append(f"### {name} ({file_path})\n```\n{code}\n```\n")
    
    if graph_context:
        sections.append("## Relationships\n")
        for ctx in graph_context[:5]:
            node = ctx.get('n', {})
            name = node.get('name', '') if node else ''
            outgoing = ctx.get('outgoing', [])
            incoming = ctx.get('incoming', [])
            if name:
                for out in outgoing[:3]:
                    if out.get('target'):
                        sections.append(f"- {name} -{out.get('rel')}-> {out['target']}\n")
                for inc in incoming[:3]:
                    if inc.get('source'):
                        sections.append(f"- {inc['source']} -{inc.get('rel')}-> {name}\n")
    
    return "\n".join(sections)
```

**Verification:**
```bash
uv run repo explain "parser"
uv run repo explain "authentication"
uv run repo explain "how does indexing work"
```

Each should return a response — even if the LLM is not configured, the context assembly should not fail. If Ollama is not installed it should say "LLM not available, showing raw context" rather than crashing.

---

## Fix 5 — Fix the Architecture Command

**File to fix:** `core/analysis/architecture_generator.py` and `core/graph/queries/architecture.py`

**The problem:** Architecture outputs empty `graph TD` because the query looks for relationships that do not exist yet (EXTENDS, IMPLEMENTS). After Fix 2 creates those relationships, the architecture query needs to be rebuilt to use what actually exists.

**What to build:** A robust architecture query that works with partial graph data and degrades gracefully:

```python
# core/graph/queries/architecture.py

ARCHITECTURE_QUERY = """
// Get all classes and their files
MATCH (f:File)-[:CONTAINS]->(c:Class)
OPTIONAL MATCH (c)-[:EXTENDS]->(parent:Class)
OPTIONAL MATCH (c)-[:IMPLEMENTS]->(iface:Interface)
OPTIONAL MATCH (c)-[:CONTAINS]->(method:Function)-[:CALLS]->(target:Function)
                <-[:CONTAINS]-(other_class:Class)
WHERE other_class <> c

RETURN 
    c.name as class_name,
    c.file_path as file_path,
    f.path as file,
    collect(distinct parent.name) as extends,
    collect(distinct iface.name) as implements,
    collect(distinct other_class.name) as calls_into
ORDER BY class_name
LIMIT 100
"""

MODULE_DEPENDENCY_QUERY = """
MATCH (a:File)-[:IMPORTS]->(b:Module)
WHERE b.name IS NOT NULL
RETURN a.path as from_file, b.name as to_module
LIMIT 100
"""
```

Then in the architecture generator, build the Mermaid diagram from whatever data comes back — even if EXTENDS is empty, show the CALLS relationships:

```python
def generate_mermaid(self, class_data: list, module_data: list) -> str:
    lines = ["graph TD"]
    added_nodes = set()
    
    # Add class nodes
    for item in class_data:
        name = item.get('class_name', '')
        if name and name not in added_nodes:
            safe_name = name.replace('-', '_').replace('.', '_')
            lines.append(f"    {safe_name}[{name}]")
            added_nodes.add(name)
    
    # Add inheritance edges
    for item in class_data:
        name = item.get('class_name', '')
        for parent in item.get('extends', []):
            if parent and name:
                safe_name = name.replace('-', '_').replace('.', '_')
                safe_parent = parent.replace('-', '_').replace('.', '_')
                if parent not in added_nodes:
                    lines.append(f"    {safe_parent}[{parent}]")
                    added_nodes.add(parent)
                lines.append(f"    {safe_name} -->|extends| {safe_parent}")
    
    # Add call edges
    for item in class_data:
        name = item.get('class_name', '')
        for called in item.get('calls_into', []):
            if called and name and called != name:
                safe_name = name.replace('-', '_').replace('.', '_')
                safe_called = called.replace('-', '_').replace('.', '_')
                lines.append(f"    {safe_name} -->|calls| {safe_called}")
    
    # If nothing was generated, add a helpful message
    if len(lines) == 1:
        lines.append("    note[No architecture data - run repo index first]")
    
    return "\n".join(lines)
```

**Verification:**
```bash
uv run repo architecture
```

Should output a non-empty Mermaid diagram with at least the class nodes visible. It does not need to be perfect — it needs to not be empty.

---

## Fix 6 — Implement Git Intelligence

**File to fix:** `core/parser/git_ingestor.py`

**The problem:** Git ingestor exists but is not populating Developer and Commit nodes in Neo4j, which is why metrics show all zeros.

**What to build:** A working git ingestor that reads the repo's git history and writes it to Neo4j.

```python
# core/parser/git_ingestor.py

import git
from pathlib import Path
from datetime import datetime
from typing import List, Dict

class GitIngestor:
    
    def __init__(self, repo_path: str, graph_client):
        self.repo_path = Path(repo_path)
        self.graph_client = graph_client
    
    async def ingest(self) -> Dict:
        """Read git history and write Developer + Commit nodes to Neo4j."""
        
        try:
            repo = git.Repo(self.repo_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            return {"status": "not_a_git_repo", "commits": 0, "developers": 0}
        
        commits_processed = 0
        developers = {}
        file_churn = {}  # file_path -> commit count
        
        # Read last 500 commits (enough for meaningful analysis)
        commits = list(repo.iter_commits(max_count=500))
        
        for commit in commits:
            author_email = commit.author.email or "unknown"
            author_name = commit.author.name or "unknown"
            commit_hash = commit.hexsha[:8]
            commit_date = datetime.fromtimestamp(commit.committed_date).isoformat()
            commit_message = commit.message.strip()[:200]
            
            # Track developers
            if author_email not in developers:
                developers[author_email] = {
                    "name": author_name,
                    "email": author_email,
                    "commit_count": 0
                }
            developers[author_email]["commit_count"] += 1
            
            # Track file churn
            try:
                for file_path in commit.stats.files.keys():
                    if file_path not in file_churn:
                        file_churn[file_path] = {
                            "count": 0, 
                            "last_author": author_email,
                            "last_modified": commit_date
                        }
                    file_churn[file_path]["count"] += 1
                    file_churn[file_path]["last_author"] = author_email
                    file_churn[file_path]["last_modified"] = commit_date
            except Exception:
                pass  # Some commits have no file stats
            
            commits_processed += 1
        
        # Write developers to Neo4j
        async with self.graph_client.session() as session:
            for email, dev in developers.items():
                await session.run("""
                    MERGE (d:Developer {email: $email})
                    SET d.name = $name,
                        d.commit_count = $commit_count
                """, email=email, name=dev["name"], 
                    commit_count=dev["commit_count"])
        
        # Write file churn to Neo4j File nodes
        async with self.graph_client.session() as session:
            for file_path, churn in file_churn.items():
                await session.run("""
                    MATCH (f:File) 
                    WHERE f.path ENDS WITH $file_path
                    SET f.churn_count = $count,
                        f.last_modified = $last_modified,
                        f.last_author = $last_author
                """, file_path=file_path, 
                    count=churn["count"],
                    last_modified=churn["last_modified"],
                    last_author=churn["last_author"])
        
        # Write OWNED_BY relationships based on who committed most to each file
        async with self.graph_client.session() as session:
            for file_path, churn in file_churn.items():
                await session.run("""
                    MATCH (f:File)
                    WHERE f.path ENDS WITH $file_path
                    MATCH (d:Developer {email: $author_email})
                    MERGE (f)-[:OWNED_BY]->(d)
                """, file_path=file_path, 
                    author_email=churn["last_author"])
        
        return {
            "status": "success",
            "commits_processed": commits_processed,
            "developers": len(developers),
            "files_with_churn": len(file_churn)
        }
```

**Wire this into the index pipeline** in `core/indexer/pipeline.py` so it runs automatically after the graph is built:

```python
# In IndexPipeline.run(), after graph building:

from core.parser.git_ingestor import GitIngestor

git_ingestor = GitIngestor(repo_path, self.graph_client)
git_result = await git_ingestor.ingest()
logger.info(f"Git intelligence: {git_result}")
```

**Verification:**
```bash
# Re-index to populate git data
uv run repo index .

# Check Neo4j for developer nodes
# In Neo4j browser: MATCH (d:Developer) RETURN d LIMIT 10

# Check metrics now have values
uv run repo metrics
```

Metrics should now show non-zero change_frequency values for files that have been modified in git history.

---

## Fix 7 — Fix the Qdrant Version Mismatch

**File to fix:** `docker-compose.yml`

**The problem:** Qdrant client is version 1.18.0 but the Docker image is serving 1.10.1. Some API calls may fail silently.

**Fix:** Update the Qdrant Docker image to match the client version:

```yaml
# In docker-compose.yml, find the qdrant service and update:
qdrant:
  image: qdrant/qdrant:v1.9.0
  # Use a version that matches or is slightly below your client
  # Client 1.18.0 is compatible with server 1.9.x
```

Or alternatively pin the client version in `pyproject.toml` to match the server:

```toml
# In pyproject.toml
qdrant-client = ">=1.9.0,<1.11.0"
```

Then:
```bash
docker-compose down qdrant
docker-compose up -d qdrant
uv sync
```

**Verification:**
```bash
curl http://localhost:6333
# Should show version that aligns with client
uv run repo search "parser"
# Should work without any version warnings in logs
```

---

## Fix 8 — Switch to Smaller Embedding Model

**File to fix:** `core/search/embedder.py` and `.repo-intel/config.toml`

**The problem:** BGE-M3 is 2GB+. For a development tool this is too heavy. It slows down first-time setup significantly.

**Fix:** Switch default to `all-MiniLM-L6-v2` which is 90MB and still excellent for code search. Keep BGE-M3 as an optional config for users who want maximum quality.

```python
# core/search/embedder.py

DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 90MB, fast, good quality
QUALITY_MODEL = "BAAI/bge-m3"        # 2GB, slower, best quality

class EmbeddingPipeline:
    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.model = None  # Lazy load
    
    def _load_model(self):
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
        return self.model
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        model = self._load_model()
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()
```

Update `config.toml` default:
```toml
[search]
embedding_model = "all-MiniLM-L6-v2"
# For better quality at cost of speed and disk space:
# embedding_model = "BAAI/bge-m3"
```

**Important:** After changing the model you must re-index. The vector dimensions change between models and old vectors are incompatible.

```bash
# Drop Qdrant collection and re-index
docker-compose restart qdrant
uv run repo index . --force
```

**Verification:**
```bash
uv run repo search "parser"
# Should return results quickly with no 2GB download
```

---

## After All 8 Fixes — Full Verification

Run these commands in order. Every single one should produce meaningful output.

```bash
# 1. Re-index with all fixes applied
uv run repo index .

# 2. Trace - should now work for classes and functions
uv run repo trace PythonParser
uv run repo trace BaseParser

# 3. Impact - was working, verify still works
uv run repo impact PythonParser
uv run repo impact BaseParser

# 4. Search - was working, verify still works
uv run repo search "parser"
uv run repo search "error handling"
uv run repo search "graph database"

# 5. Architecture - should now show real nodes
uv run repo architecture

# 6. Metrics - should now show non-zero values for git-tracked files
uv run repo metrics

# 7. Explain - should now work via semantic search fallback
uv run repo explain "parser"
uv run repo explain "how does indexing work"

# 8. Dead code - should now be more accurate
uv run repo dead-code

# 9. Onboard - was working, verify still works
uv run repo onboard
```

---

## Neo4j Verification Queries

After fixing and re-indexing, run these in the Neo4j browser at `http://localhost:7474`:

```cypher
// Check all relationship types exist
MATCH ()-[r]->() 
RETURN type(r) as relationship_type, count(r) as count
ORDER BY count DESC

// Expected output should include:
// CONTAINS - high count
// CALLS - moderate count  
// IMPORTS - moderate count
// EXTENDS - should now exist
// OWNED_BY - should now exist (after git ingest)

// Check developer nodes
MATCH (d:Developer) RETURN d.name, d.email, d.commit_count ORDER BY d.commit_count DESC LIMIT 10

// Check file churn is populated
MATCH (f:File) WHERE f.churn_count IS NOT NULL 
RETURN f.path, f.churn_count ORDER BY f.churn_count DESC LIMIT 10

// Check class inheritance works
MATCH (c:Class)-[:EXTENDS]->(parent:Class)
RETURN c.name, parent.name LIMIT 20
```

---

## Run the Full Test Suite

```bash
# Unit tests
uv run pytest tests/unit/ -v

# Integration tests (needs Docker running)
uv run pytest tests/integration/ -v

# Full suite
uv run pytest tests/ -v

# Linter
uv run ruff check .

# Auto-fix linting issues
uv run ruff check . --fix
```

All tests should pass. If integration tests fail after fixes, add new tests for the fixed functionality rather than deleting failing tests.

---

## After All Fixes Pass — Build the MCP Server

Once all 8 fixes are verified working, the next major feature to build is the MCP server. This is what connects RIP to Claude Code, Codex, and other AI agents.

**Create a new file:** `mcp/server.py`

Expose only the commands that are now fully working:

```python
# mcp/server.py

"""
RIP MCP Server - exposes repository intelligence as MCP tools
for Claude Code, Codex, Cursor, and any MCP-compatible agent.

Start with: uv run python mcp/server.py
Add to Claude settings:
{
  "mcpServers": {
    "rip": {
      "command": "uv",
      "args": ["run", "python", "mcp/server.py"],
      "cwd": "/path/to/your/rip/installation"
    }
  }
}
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

# MCP tools to expose - only expose what is verified working
TOOLS = {
    "repo_search": {
        "description": "Semantic search across the codebase. Finds code by meaning not just keywords. Use this to find where something is implemented.",
        "parameters": {
            "query": {"type": "string", "description": "What to search for"},
            "top_k": {"type": "integer", "description": "Number of results", "default": 10}
        }
    },
    "repo_impact": {
        "description": "Find everything that depends on a symbol. Use before modifying anything to understand what will break.",
        "parameters": {
            "symbol": {"type": "string", "description": "Class or function name to analyse"}
        }
    },
    "repo_trace": {
        "description": "Trace the call chain from a symbol. Shows how execution flows through the codebase.",
        "parameters": {
            "symbol": {"type": "string", "description": "Starting point for trace"}
        }
    },
    "repo_onboard": {
        "description": "Get a complete overview of the repository architecture, entry points, and key modules.",
        "parameters": {}
    },
    "repo_explain": {
        "description": "Get a plain English explanation of how a feature or component works.",
        "parameters": {
            "topic": {"type": "string", "description": "What to explain"}
        }
    }
}

def run_rip_command(command: str, args: list = []) -> str:
    """Run a RIP CLI command and return its output."""
    cmd = ["uv", "run", "repo", command] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent)
        )
        output = result.stdout
        if result.returncode != 0 and result.stderr:
            output += f"\nWarning: {result.stderr[:200]}"
        return output or f"No output from repo {command}"
    except subprocess.TimeoutExpired:
        return f"Command timed out: repo {command}"
    except Exception as e:
        return f"Error running repo {command}: {str(e)}"

async def handle_tool_call(tool_name: str, parameters: dict) -> str:
    """Handle an MCP tool call and return the result."""
    
    if tool_name == "repo_search":
        query = parameters.get("query", "")
        top_k = parameters.get("top_k", 10)
        return run_rip_command("search", [query, "--top", str(top_k)])
    
    elif tool_name == "repo_impact":
        symbol = parameters.get("symbol", "")
        return run_rip_command("impact", [symbol])
    
    elif tool_name == "repo_trace":
        symbol = parameters.get("symbol", "")
        return run_rip_command("trace", [symbol])
    
    elif tool_name == "repo_onboard":
        return run_rip_command("onboard")
    
    elif tool_name == "repo_explain":
        topic = parameters.get("topic", "")
        return run_rip_command("explain", [topic])
    
    else:
        return f"Unknown tool: {tool_name}"

async def main():
    """Simple stdio MCP server."""
    
    # Send capabilities on startup
    capabilities = {
        "jsonrpc": "2.0",
        "result": {
            "capabilities": {
                "tools": {}
            }
        }
    }
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
            method = request.get("method", "")
            request_id = request.get("id")
            
            if method == "tools/list":
                tool_list = []
                for name, info in TOOLS.items():
                    tool_list.append({
                        "name": name,
                        "description": info["description"],
                        "inputSchema": {
                            "type": "object",
                            "properties": info.get("parameters", {})
                        }
                    })
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tool_list}
                }
            
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                
                result_text = await handle_tool_call(tool_name, tool_args)
                
                response = {
                    "jsonrpc": "2.0", 
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}]
                    }
                }
            
            elif method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "rip", "version": "1.0.0"}
                    }
                }
            
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            
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

if __name__ == "__main__":
    asyncio.run(main())
```

**Test the MCP server:**
```bash
# Test it starts without error
uv run python mcp/server.py &
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | uv run python mcp/server.py
```

**Connect to Claude Code** by adding to your Claude configuration:
```json
{
  "mcpServers": {
    "rip": {
      "command": "uv",
      "args": ["run", "python", "mcp/server.py"],
      "cwd": "C:\\Users\\Dell\\Downloads\\RIP"
    }
  }
}
```

---

## Priority Order Summary

Do these in exact order. Do not skip. Do not move to the next until the current one is verified.

```
1. Fix trace engine query              → repo trace works
2. Fix graph builder relationships     → EXTENDS, IMPLEMENTS appear in Neo4j
3. Fix Python parser inheritance       → Classes know their parents
4. Fix explain command                 → repo explain works via search fallback
5. Fix architecture command            → repo architecture shows real data
6. Implement git intelligence          → repo metrics shows non-zero values
7. Fix Qdrant version mismatch        → No version warnings in logs
8. Switch to smaller embedding model   → Fast setup, 90MB not 2GB

Then:
9. Build MCP server                    → Claude Code can use RIP as tools
10. Run full test suite                → Everything green
11. Run ruff check                     → No linting errors
```

---

## What NOT to Build Right Now

Skip these until the above fixes are complete and verified:

- SaaS frontend (Next.js, dashboard, user accounts)
- Payment integration
- Multi-tenancy
- Prometheus / Grafana monitoring  
- Celery background workers
- GitHub/GitLab OAuth integration
- Production deployment (Docker Swarm, Kubernetes)
- Any new CLI commands beyond what is already stubbed

The system needs to be solid and reliable before it needs to be scalable or multi-tenant.

---

## Definition of Done for This Phase

You are done with this phase when all of these are true simultaneously:

```
uv run repo trace PythonParser        → returns actual call chain
uv run repo trace BaseParser          → returns actual connections
uv run repo architecture              → shows non-empty Mermaid diagram
uv run repo metrics                   → shows non-zero values for some files
uv run repo explain "parser"          → returns meaningful explanation
uv run repo impact PythonParser       → still works (regression check)
uv run repo search "parser"           → still works (regression check)
uv run repo onboard                   → still works (regression check)
uv run pytest tests/ -v               → all tests pass
uv run ruff check .                   → clean
MCP server starts without error       → connects to Claude Code
```

When all twelve of these pass, RIP has gone from a 70% complete prototype to a fully functional repository intelligence platform ready for real use and ready to connect to AI coding agents.