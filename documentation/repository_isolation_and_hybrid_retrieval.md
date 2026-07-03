# Repository Isolation and Hybrid Retrieval

## Repository Isolation

RIP treats every indexed repository as a project. The project id is deterministic from
the resolved repository root and is also stored in the SQL metadata table `projects`.

Storage ownership:

- PostgreSQL stores `Project(id, name, root, language, created_at)`.
- Neo4j stores `(:Project {id})` and connects it to files with `CONTAINS`.
- Neo4j connects `Project` to entities with `OWNS`.
- Every `File`, `Class`, `Function`, `Module`, `Widget`, API, and relationship-owned
  entity carries `project_id`.
- Qdrant payloads carry `project_id` and `project_name`.

Neo4j uses composite uniqueness for `(project_id, path)` and `(project_id, fqn)` so
two repositories can contain the same file path or symbol name without collision.
Graph queries must either start from `Project {id}` or filter nodes with
`project_id = $project_id`.

Qdrant uses one shared collection with payload filtering:

```python
Filter(
    must=[
        FieldCondition(
            key="project_id",
            match=MatchValue(value=project_id),
        )
    ]
)
```

This is preferred over one collection per repository because it keeps migrations,
embedding model upgrades, and runtime client reuse simple while preserving strict
query isolation. Separate collections remain a future option for very large tenants
or hard operational isolation.

## Active Project CLI

Use `repo projects` to list indexed projects. Use `repo use <project-id>` to store the
active project in `.repo-intel/active_project`. Read commands accept `--project` to
override that active value.

Examples:

```bash
repo projects
repo use 3f2f...
repo search auth --project 3f2f...
repo explain AuthService --project 3f2f...
```

## Hybrid Retrieval

`Searcher.hybrid_search()` is project-scoped and rejects calls without a project id.
The retrieval pipeline is:

1. Vector retrieval from Qdrant with mandatory `project_id` payload filter.
2. Lexical retrieval from Neo4j over names, FQNs, docstrings, and compact code.
3. Graph expansion for calls, imports, dependencies, inheritance, implementations,
   and containment within the same project.
4. Candidate merge and de-duplication by entity id.
5. Cross-encoder reranking.
6. Compressed explain context with component summaries, dependencies, related
   components, and relationship evidence instead of full raw file dumps.

All expansion queries filter by `project_id`, so duplicate symbols in another
repository cannot enter the candidate pool unless a future explicit cross-project
feature deliberately asks for it.
