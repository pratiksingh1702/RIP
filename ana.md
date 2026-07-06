RIP + Context Gateway: Complete Implementation Documentation

From Concept to Production — Every Detail, Every Decision, Every Example

---

BOOK ONE: THE FOUNDATION

---

Chapter 1: What We Built and Why

1.1 The Problem That Started Everything

In 2024, software development reached an inflection point. AI coding assistants like GitHub Copilot, Cursor, Claude Code, and Codex had become mainstream. Developers could generate code faster than ever before. But a new bottleneck emerged that no one had anticipated: understanding existing code became harder than writing new code.

A senior developer at a mid-sized fintech company described her daily reality: "I spend four hours reading code for every one hour I spend writing it. I open forty-seven files across eight microservices just to trace how a payment flows through the system. I ask three different colleagues questions because the original authors left the company. And when I finally understand the system enough to make a change, I realize another team just modified the same function for a different feature, and now we have a merge conflict."

This wasn't an isolated experience. Across the industry, developers were drowning in context. The tools that promised to help — keyword search, IDE navigation, simple vector search — all operated at the text level. They understood files but not architecture. They understood words but not relationships. They could find a function named processPayment but couldn't tell you that changing it would break the refund system, the notification service, and the regulatory compliance checker.

Meanwhile, organizations were adopting multiple AI coding assistants simultaneously. One team preferred Claude for architectural reasoning. Another team used GPT for implementation. A third used Gemini for documentation. Each AI agent operated in isolation, unaware of what the others were doing. They duplicated context retrieval. They consumed massive token windows with redundant information. They had no shared memory of past investigations. And critically, they operated with no organizational governance — no permissions, no approval chains, no audit trails, no way to ensure that AI-generated code followed the company's security policies and engineering standards.

The problem had shifted. It was no longer "Can AI write good code?" It was now "How do we orchestrate dozens of AI agents, hundreds of developers, and millions of lines of code without chaos?"

1.2 The Two-Part Answer

Our answer came in two parts, each solving a different layer of the problem.

Repository Intelligence Platform (RIP) was built to solve the understanding problem. Instead of treating a repository as a flat collection of files, RIP models it as a living, interconnected system. Through abstract syntax tree parsing, semantic embeddings, and knowledge graph construction, RIP converts implicit architectural knowledge into explicit, queryable intelligence. It understands that PaymentProcessor.validate() calls CurrencyConverter.convert(), which depends on ExchangeRateService.fetch(), which is called by six different API endpoints, three of which are public-facing and two of which handle regulatory reporting. It can answer questions like "What breaks if I change this function?" not with AI hallucination, but with verifiable evidence from the actual codebase graph.

Context Gateway was built to solve the orchestration and governance problem. Instead of every AI agent independently searching repositories, querying tools, and assembling context, all interactions flow through a centralized Gateway. The Gateway classifies developer intent, plans retrieval strategies, executes queries across multiple information sources simultaneously, ranks and deduplicates results, compresses them into optimized token budgets, enforces permission boundaries, maintains session memory, detects conflicts between concurrent sessions, and delivers precisely the context an AI agent needs — no more, no less.

But as we built and deployed these systems with real teams, a deeper realization emerged. The Gateway was solving context optimization, but organizations needed something more fundamental: a control plane for how AI operates within their software engineering lifecycle.

1.3 The Evolution: From Context Optimizer to Control Plane

The insight came from watching how different teams used the Gateway. A payment team at a fintech company had strict rules: AI could suggest code changes but never modify payment logic directly. A security team at a defense contractor required that all AI analysis of authentication code happen on-premise, with no data leaving their network. A frontend team at a startup wanted AI to auto-merge simple UI fixes if tests passed, but required human review for anything touching user data.

Each team was inventing their own processes, their own rules, their own workflows. The Gateway was providing context, but the teams were manually orchestrating everything around it. They were writing lengthy prompts every time, repeating the same instructions, manually checking permissions, and separately documenting their decisions.

The Gateway needed to evolve from a context delivery system into a workflow execution system. From a tool that developers query into a platform that organizations configure. From a context optimizer into a control plane.

This evolution preserved everything the Gateway already did — every classifier, every planner, every retriever, every ranker, every compressor, every permission check, every audit log. But it added a new layer above: workflows that define how engineering tasks should be executed, prompt templates that become reusable organizational assets, approval gates that enforce review policies, organizational memory that compounds knowledge over time, session coordination that prevents conflicts before they happen, and a mobile interface that lets developers trigger, monitor, and approve workflows from anywhere.

---

Chapter 2: Repository Intelligence Platform — The Eyes Into the Codebase

2.1 What RIP Understands That Other Tools Don't

Traditional code search tools work like Google for your codebase. You type keywords, they return files containing those keywords. This works for simple lookups — finding where a variable is defined, locating a specific error message. But it fails catastrophically for architectural understanding.

Consider a real scenario from our design partner, a fintech company with a 3-year-old codebase and 200 developers. A developer was tasked with fixing a bug: "International transfers over $10,000 are failing with a regulatory limit error." A keyword search for "regulatory limit" returned 47 files. The actual bug was a one-line fix in CurrencyConverter.ts where Math.floor() should have been Math.round(). The developer spent three days finding this because no search tool could tell them: "The regulatory limit check happens in CurrencyConverter, which is called by the transfer route, the payment handler, and the refund service. The limit was added 3 months ago by a developer who has since left the company. Here's the exact dependency chain and the commit history."

RIP solves this by building a comprehensive understanding of the repository before any questions are asked. It doesn't index text; it models architecture.

2.2 How RIP Parses and Models Code

When RIP indexes a repository, it performs several layers of analysis, each building on the previous one.

Layer 1: Abstract Syntax Tree Parsing

RIP uses Tree-sitter parsers to build ASTs for every source file. Unlike regex-based tools that treat code as text, AST parsing understands the grammatical structure of the programming language. RIP has production-quality parsers for Python, TypeScript, Java, Go, Rust, and Dart (including Flutter widget recognition). When it parses a TypeScript file, it doesn't just see characters — it sees class declarations, method signatures, parameter types, inheritance hierarchies, import statements, and function calls.

For example, when RIP parses this TypeScript code:

```typescript
export class PaymentProcessor {
  constructor(private currencyConverter: CurrencyConverter) {}
  
  async processPayment(amount: number, currency: string): Promise<PaymentResult> {
    const convertedAmount = await this.currencyConverter.convert(amount, currency);
    return this.executePayment(convertedAmount);
  }
}
```

It extracts structured entities: a class named PaymentProcessor with a constructor dependency on CurrencyConverter, a method processPayment that calls currencyConverter.convert(), and a return type of PaymentResult. These aren't just strings — they're typed entities with relationships.

Layer 2: Graph Construction

The extracted entities and relationships are written to a knowledge graph. In production deployments, this is Neo4j. For local development, it's NetworkX. The graph is project-scoped, meaning every node and edge carries a project_id that enables multi-project queries without cross-contamination.

The graph captures relationship types that go far beyond simple "calls" edges:

· CALLS: Function A calls Function B
· EXTENDS: Class A inherits from Class B
· IMPLEMENTS: Class A implements Interface B
· IMPORTS: File A imports Module B
· DEPENDS_ON: Service A depends on Service B
· CONTAINS: Module A contains Class B
· HANDLES: Controller A handles Route B
· PROVIDES: Service A provides Interface B
· CONSUMES: Component A consumes Context B

For our payment processor example, the graph would contain nodes for PaymentProcessor, CurrencyConverter, PaymentResult, and edges showing that PaymentProcessor depends on CurrencyConverter and produces PaymentResult. If another service also depends on CurrencyConverter, that relationship is captured too. Over time, the graph becomes a complete map of the software system — not documentation that someone wrote and forgot to update, but a living model derived from the actual code.

Layer 3: Semantic Embedding

Simultaneously, RIP generates vector embeddings for code entities. These embeddings capture semantic meaning, enabling search based on conceptual similarity rather than exact text matching. A developer searching for "payment validation logic" will find validateAmount(), checkLimits(), and verifyCurrency() even though none of those functions contain the word "validation" in their names or bodies.

The embeddings are generated using a configurable model (defaulting to a code-optimized embedding model) and cached by content hash, so re-indexing unchanged files is free. The vector store is Qdrant in production and FAISS or NumPy-based fallback in local mode.

Layer 4: Hybrid Search

RIP's search capability combines all three layers. A query goes through BM25 keyword matching (for exact term matches), semantic vector search (for conceptual similarity), and graph expansion (for architectural context). The reranker then scores and merges results, ensuring the most architecturally relevant entities surface to the top.

When our fintech developer searched for "regulatory limit," RIP's hybrid search would return CurrencyConverter.convert() as the top result because:

· BM25 matched "limit" in the function body (the amount check)
· Semantic search recognized that "regulatory" is conceptually related to limit enforcement
· Graph expansion showed that this function is the central node in the payment validation chain

2.3 RIP's Analysis Capabilities

Beyond search, RIP provides a suite of analysis engines that answer specific architectural questions:

Dependency Tracing answers "What calls this, and what does this call?" For any function, class, or module, RIP can trace the complete call chain up to a configurable depth. It shows callers (what depends on this entity) and callees (what this entity depends on). This is the foundation for impact analysis — before changing any code, a developer can see exactly what will be affected.

Dead Code Detection finds functions, classes, and modules that have no incoming references in the graph. But RIP is smarter than simple reference counting. It accounts for reflection-based calls, dynamic imports, route handlers that are invoked by framework code rather than explicit calls, and public API endpoints that may be consumed externally. The analysis is conservative — it would rather flag something as "possibly dead" than confidently declare something dead that's actually used.

Architecture Generation produces visual and textual representations of system architecture. It identifies module boundaries, service dependencies, data flow patterns, and architectural violations (like circular dependencies or unauthorized cross-module calls). This isn't a static diagram that becomes obsolete — it's generated fresh from the current state of the codebase every time it's requested.

Impact Analysis combines dependency tracing with change history to predict the blast radius of a proposed change. It answers "If I change this function, what tests should I run? What teams should I notify? What deployment checks should be extra careful?"

Onboarding Engine generates personalized codebase tours for new developers. Given a team assignment, it identifies the modules that team owns, traces the key architectural patterns, and generates a progressive learning path — starting with data models, moving through API layers, into business logic, and finally to deployment configuration.

2.4 RIP's Interfaces

RIP is accessible through multiple interfaces, all backed by the same core engine:

CLI (Command Line Interface): The primary interface for individual developers. Commands like repo search "payment validation", repo explain PaymentProcessor.processPayment, repo trace CurrencyConverter.convert, and repo architecture provide immediate answers. The CLI uses lazy imports for fast startup and logs every command to per-command log files for debugging.

FastAPI Server: A persistent server that exposes REST and WebSocket endpoints. The server supports API key authentication (both environment variable and database-backed with hashing, expiry, and revocation), project-scoped queries, remote Git repository cloning with background indexing, and live progress streaming via WebSocket. This is what the Gateway, VS Code extension, and mobile app connect to.

MCP Server: An implementation of the Model Context Protocol that exposes RIP's capabilities as tools callable by AI agents. Tools include search, trace, impact, explain, onboard, architecture, and metrics. Any MCP-compatible AI agent can query RIP directly without custom integration code.

VS Code Extension: A chat-first sidebar that provides RIP access within the editor. It supports all CLI commands as chat messages (with /search, /explain, /trace command parsing), live terminal streaming for long-running operations, and contextual awareness of the currently open file.

Flutter Mobile App: A chat-first Android client that connects to the RIP server. It provides all the same capabilities as the CLI and VS Code extension, plus project switching, history browsing, and integration with the Gateway for workflow execution.

2.5 Runtime Modes

RIP is designed to run anywhere, from a developer's laptop to a production server cluster.

Local Mode requires nothing beyond Python. It uses SQLite for metadata, NetworkX for graph storage, and FAISS or NumPy for vector search. No Docker, no external services, no network dependencies. A developer can clone a repository and start querying it within minutes.

Server Mode uses Docker Compose to run Neo4j, Qdrant, and PostgreSQL alongside the RIP server. This enables multi-user access, larger repositories, and persistent indexing across restarts. The server serves the REST API, WebSocket connections, and the Gateway.

Capability Detection ensures graceful degradation. RIP detects which services are available and enables or disables features accordingly. If Neo4j isn't running, graph queries fall back to NetworkX. If Qdrant isn't available, vector search falls back to FAISS. The repo doctor command diagnoses the current environment and suggests upgrades.

---

Chapter 3: Context Gateway — The Brain That Orchestrates Everything

3.1 The Original Gateway: Context Optimization Pipeline

The Context Gateway began as a context optimization engine. Its job was simple to describe but complex to implement: when an AI agent needs context about a codebase, don't just dump files at it. Instead, understand what the agent is trying to do, figure out what information would be most useful, gather that information from all available sources, rank and deduplicate it, compress it to fit within token limits, apply permission filters, and deliver it.

This pipeline has eight stages, each implemented as a modular, testable component:

Stage 1: Intent Classification

When a request arrives at the Gateway, the first question is: "What is the developer actually trying to do?" A request about "fixing the payment bug" requires different context than "explain how authentication works" or "add a CSV export feature."

The classifier uses a rule-based system as its primary engine. It analyzes the request text for intent-signaling patterns: bug-related keywords ("fix," "broken," "error," "bug"), feature-related language ("add," "implement," "create new"), architectural questions ("how does X work," "explain the architecture"), and investigation patterns ("why is," "what causes," "trace the flow").

It also detects domain hints: "payment," "auth," "database," "notification," "infrastructure." These hints help the later retrieval planner know which parts of the codebase to prioritize.

When the rule-based classifier's confidence falls below a threshold, it falls back to an LLM-based classifier. This handles ambiguous or novel requests that don't match known patterns. The LLM receives a few-shot prompt with examples and returns a structured classification.

Stage 2: Retrieval Planning

Once the intent is known, the planner builds a retrieval strategy. Different intents require different information sources and different query formulations.

For a bug fix intent, the plan might be:

· Query RIP for code related to the bug description (priority: critical)
· Query GitHub for recent commits touching those files (priority: high)
· Query Jira for related bug tickets (priority: medium)
· Query Slack for recent discussions about the affected module (priority: low)

For an architectural question:

· Query RIP for architecture overview of the mentioned system (priority: critical)
· Query RIP for dependency tracing of key components (priority: high)
· Query documentation systems for design documents (priority: medium)

The planner allocates token budgets to each source, ensuring the total retrieved context fits within the model's context window while giving more space to higher-priority sources.

RIP's explain endpoint is treated as a required, first-run priority query in every plan. This ensures that the AI agent always receives a structured explanation of the relevant code before any raw search results.

Stage 3: Parallel Execution

The Gateway executes the retrieval plan by querying all sources in parallel. Each source is wrapped in a standardized interface (the BaseSource protocol), whether it's RIP running as a local subprocess, GitHub's API, a Jira instance, or a user-registered MCP server.

The executor handles the complexities of distributed retrieval: exponential backoff retry for transient failures, circuit breakers that stop querying a failing source after repeated errors, per-source timeouts, and graceful degradation when sources are unavailable. If Jira is down, the Gateway doesn't fail — it returns context from the sources that are available and notes which sources were skipped.

Stage 4: Context Ranking

The raw results from all sources are merged and scored. The ranker uses a weighted algorithm considering multiple factors:

· Semantic similarity: How closely does the retrieved content match the original query? Computed using embedding similarity.
· Architectural centrality: In the RIP dependency graph, how central is this entity? A function called by 50 other functions is more important than one called by 2.
· Recency: When was this code last changed? Recent changes are more likely relevant to current bugs.
· Pattern matching: Does this code follow patterns known to be relevant to the detected intent?
· Source authority: Results from RIP (grounded in actual code structure) are weighted higher than results from Slack discussions (which may be outdated opinions).

Stage 5: Deduplication

Multiple sources often return the same information. A file might appear in RIP search results, GitHub commit history, and a Slack discussion. The deduplicator identifies these overlaps using content hashing and near-duplicate detection, keeping the highest-quality version and discarding redundancies.

Stage 6: Token Compression

The ranked, deduplicated context must fit within the target model's token budget. The compressor applies several strategies:

· Truncating low-priority content while preserving high-priority content in full
· Summarizing verbose code sections while keeping critical function signatures intact
· Removing comments and whitespace when necessary (but preserving docstrings for public APIs)
· Prioritizing architectural relationships (dependency graphs) over implementation details

If even after compression the context exceeds the budget, an overflow summarizer generates a condensed version of the lowest-priority content.

Stage 7: Permission Filtering

Before any context is returned, it passes through the permission engine. This ensures that sensitive information isn't leaked to unauthorized users or AI agents.

The permission model is role-based: junior_dev, developer, senior_dev, and ci_agent. Each role has different access levels. Sensitive domains like payment, auth, and security have additional restrictions. A junior developer might receive code context about payment processing, but certain implementation details (API keys, encryption internals) might be redacted or summarized.

Stage 8: Session Management and Audit

Every context request is part of a session. The session engine tracks what context was provided, what files were discussed, and what decisions were made. This enables conflict detection — if two developers are working on the same files simultaneously, the Gateway can warn them.

Every action is logged to an audit trail. The audit log records who requested what context, what sources were queried, what results were returned, and what permissions were applied. This is critical for regulated industries that need to demonstrate control over AI-assisted development.

3.2 What the Gateway Already Integrates With

The Gateway's source registry is dynamic and extensible. It's not hardcoded to specific tools — any MCP-compatible server can be registered at runtime and immediately become available for context retrieval.

Built-in Sources:

· RIP: The privileged, always-on source. Connected via CLI subprocess in local mode, with query-type fallback chains for robustness.
· GitHub: Repository search, commit history, file contents, pull request details, code review comments. Authenticated via OAuth with per-user token scoping.
· Jira: Issue search, project browsing, ticket details, comment history. Authenticated via API key or OAuth.
· Slack: Message search, channel history, thread replies. Authenticated via OAuth.

Dynamic MCP Sources:

Any MCP server implementing the streamable-http, SSE, or stdio transport can be registered. The Gateway handles initialize handshakes, tools/list capability discovery, tools/call execution, and capability persistence. A user can register their internal deployment API, their custom security scanner, their database query tool, or any other MCP-compatible service, and it immediately becomes available as a context source.

OAuth Bridge:

The Gateway includes a complete OAuth 2.0 infrastructure for connecting to external services. It supports PKCE flow with state parameter verification, encrypted token storage, automatic token refresh scheduling, and reauthorization detection. Both web-based OAuth (with mobile deep-link callback capture) and CLI-based OAuth (with localhost loopback) are supported. Tokens are scoped per-user and per-project.

Credential Vault:

For services that use API keys rather than OAuth, the Gateway provides an encrypted credential vault. Credentials are encrypted at rest, never returned in plaintext via the API, and linked to specific projects through a many-to-many allocation table. The vault supports connect, disconnect, and reconnect flows with full audit logging.

3.3 The Gateway's MCP Server

The Gateway itself is an MCP server, exposing tools that AI agents can call:

· get_context: The full context pipeline — classify, plan, retrieve, rank, compress, filter, return. This is what Claude Code or Cursor would call to get intelligent context about a codebase.
· validate_change: Given a proposed code change, validates it against dependency graphs, security policies, and testing requirements.
· search_codebase: Direct semantic search across the indexed repository.
· explain_architecture: Generates an architectural explanation of a specified component or system.

This means any MCP-compatible AI agent can use the Gateway without custom integration. The agent just needs to connect to the Gateway's MCP endpoint and call tools.

---

Chapter 4: The New Architecture — Control Plane for AI Software Engineering

4.1 Why the Gateway Needed to Evolve

The original Gateway solved the context problem brilliantly. But as teams adopted it, they started using it in ways we hadn't anticipated. They weren't just asking for context — they were building processes around it.

A payment team lead described their workflow: "First, I query the Gateway for the payment processing architecture. Then I trace the dependency chain for the specific function I'm changing. Then I check GitHub for recent commits. Then I ask Claude to analyze the impact. Then I run the tests. Then I create a PR. Then I wait for my team lead to approve. Then I merge. I do this same sequence for every bug fix. I wish I could just press a button and have all of this happen automatically."

A security lead at a healthcare company had a different process: "Every month, I manually run a security audit on all authentication code. I spend three days checking dependencies, running scanners, reviewing changes, and writing reports. It's the same process every month. I've written it down, but I still have to do it manually because each step requires different tools and different contexts."

These teams were describing workflows — repeatable sequences of steps that transform a trigger into an outcome. The Gateway was providing the intelligence for each step, but the teams were manually orchestrating the steps themselves.

At the same time, organizations were grappling with governance questions that the original Gateway wasn't designed to answer:

· "How do we ensure AI-generated code is reviewed before it reaches production?"
· "How do we prevent AI from accessing sensitive repositories?"
· "How do we control which AI models are used for which types of work?"
· "How do we track what AI has done for compliance audits?"
· "How do we prevent two AI agents from modifying the same file simultaneously?"
· "How do we retain the knowledge gained from AI-assisted investigations?"

These weren't context problems. They were control plane problems.

4.2 The Block Architecture: Everything Is a Composable Unit

The foundational insight of the new architecture is that every capability in the system — every RIP query, every LLM call, every GitHub operation, every test run, every approval request, every notification — is a Block. A Block is a self-contained unit of work with a defined input schema, output schema, configuration schema, and execution contract.

```python
Block
├── id: str                     # "rip.search", "github.commits", "llm.analyze"
├── kind: BlockKind             # retrieval | tool | llm | prompt | approval | 
│                                  verification | deployment | notification | memory
├── input_schema: JSONSchema    # What inputs this block requires
├── output_schema: JSONSchema   # What outputs this block produces
├── config_schema: JSONSchema   # What configuration options it accepts
├── requires_capabilities: []   # NETWORK, GRAPH_STORE, LLM, SUBPROCESS
├── run(ctx, inputs, config) → BlockResult
└── describe() → BlockManifest  # For the UI palette and marketplace
```

This abstraction is powerful because it makes everything composable. A workflow isn't a special kind of thing — it's just blocks connected by wires. A prompt template isn't a separate system — it's a block that renders variables and feeds them to an LLM block. An approval gate isn't custom logic — it's a block whose run() method suspends the workflow until a human responds.

The existing Gateway pipeline — all eight stages from classification through audit — becomes exactly one block: context.retrieve. This means everything that currently works continues to work exactly as before. The /gateway/api/context endpoint still exists and still returns optimized context. But now that same capability can also be dropped into a workflow as a step alongside other blocks.

This is the "preserved, not replaced" principle. Nothing in the existing codebase is modified. New capability is added as new blocks that wrap around the existing pipeline.

4.3 The Block Registry: Where Blocks Come From

The Block Registry is the central catalog of all available block types. Blocks register themselves at system startup, and the registry makes them discoverable for the Workflow Engine and the UI palette.

Blocks come from five sources:

Built-in Blocks are shipped with the Gateway. They include all RIP capabilities (search, trace, impact, explain, architecture, metrics, dead code detection), all LLM operations (analyze, generate, summarize), flow control (approval gates, condition branches, loops), verification (run tests, run linter, type check), deployment (create PR, merge, create branch), notification (push notification, Slack message, email), and memory (save to organizational memory, search memory).

MCP Tool Blocks are automatically created from registered MCP sources. When a user connects a GitHub MCP server, the Gateway discovers its tools and creates corresponding blocks: github.search_code, github.get_commits, github.create_pr, etc. The user doesn't need to write any integration code — the MCP protocol handles discovery and the Gateway handles block registration.

Composite Blocks are user-created groupings of existing blocks. A developer can select five blocks on their canvas, group them into a "Full Bug Fix Pipeline" composite block, and reuse it across workflows. Composite blocks expose configurable inputs and outputs, making them first-class citizens in the palette.

Plugin Blocks are third-party blocks distributed as packages. A block.json manifest describes the block's identity, schemas, and MCP endpoint. The Plugin Manager handles installation, versioning, and sandboxing.

Custom Code Blocks allow advanced users to write custom logic. These are registered with a code snippet or a reference to a local script, executed in a sandboxed environment.

4.4 The Workflow Engine: From Trigger to Completion

The Workflow Engine is the heart of the control plane. It takes a workflow definition — a DAG of blocks connected by wires — and executes it step by step, handling parallelism, error recovery, suspension, and resumption.

Workflow Definition:

A workflow is defined as a collection of blocks and wires, plus a trigger configuration:

```yaml
workflow:
  id: bug_investigation_v2
  name: "Bug Investigation"
  category: investigation
  
  trigger:
    type: manual_query  # User types a natural language query
    extracted_params:
      - name: query
        source: full_text
      - name: repository
        source: current_project
      - name: priority
        default: medium
  
  blocks:
    - step_id: step_1
      block_type: rip.search
      config: {max_results: 10}
      input_bindings:
        - field: query
          source: trigger_query
        - field: repository
          source: trigger_param
          param: repository
    
    - step_id: step_2
      block_type: rip.trace
      config: {depth: 3, direction: both}
      input_bindings:
        - field: symbol
          source: step_output
          step: step_1
          field_path: top_result.function_name
    
    - step_id: step_3
      block_type: github.recent_commits
      input_bindings:
        - field: files
          source: step_output
          step: step_1
          field_path: files
        - field: days
          source: fixed
          value: 30
    
    - step_id: step_4
      block_type: llm.analyze
      config: {temperature: 0.3, max_tokens: 4096}
      input_bindings:
        - field: code_context
          source: step_output
          step: step_1
        - field: dependency_graph
          source: step_output
          step: step_2
        - field: recent_changes
          source: step_output
          step: step_3
    
    - step_id: step_5
      block_type: approval.gate
      config:
        condition: role_based
        require_role: senior_dev
        timeout_hours: 24
  
  wires:
    - from: {step: step_1, port: output}
      to: {step: step_2, port: symbol}
    - from: {step: step_1, port: output}
      to: {step: step_3, port: files}
    - from: {step: step_1, port: output}
      to: {step: step_4, port: code_context}
    - from: {step: step_2, port: output}
      to: {step: step_4, port: dependency_graph}
    - from: {step: step_3, port: output}
      to: {step: step_4, port: recent_changes}
    - from: {step: step_4, port: output}
      to: {step: step_5, port: context}
```

Execution Flow:

When a user triggers this workflow by typing "international transfers over $10,000 failing with regulatory limit error," the Workflow Engine:

1. Creates a WorkflowRun record with status pending
2. Snapshots the entire workflow definition (blocks, wires, configs) so the run is immutable even if the workflow is later edited
3. Resolves the trigger: extracts parameters from the natural language query
4. Builds the execution DAG: determines which steps depend on which other steps
5. Begins executing ready steps (those with no unmet dependencies)

For each step, the engine:

1. Resolves input bindings: follows the wires to get data from previous steps or trigger parameters
2. Validates inputs against the block's input schema
3. Creates an execution context (user identity, project, event bus, storage)
4. Calls the block's run() method with resolved inputs and config
5. Handles the result: completed, failed, or suspended

If a block returns suspended (like an approval gate), the entire workflow pauses. The engine persists the current state and waits for an external signal — a POST /approve call from a mobile device or web interface. When the signal arrives, the engine resumes from the suspended step.

If a block fails, the engine applies the retry policy. If retries are exhausted, the workflow fails. The error is recorded with the step that failed, the inputs that were provided, and the error message, making debugging straightforward.

Parallel Execution:

Steps that don't depend on each other run in parallel. In the example above, steps 2 and 3 both depend on step 1 but not on each other, so they execute simultaneously. The engine tracks completion of parallel steps and unblocks downstream steps as soon as all their dependencies are satisfied.

4.5 The Prompt Engine: Prompts as Organizational Assets

Before the Prompt Engine, prompts were inline strings scattered across the codebase. A developer would write "You are analyzing a bug in {repo}. Use the provided context..." directly in their code or paste it into a chat window. Every time they needed the same prompt, they'd write it again — or copy-paste and forget to update it.

The Prompt Engine transforms prompts from ad-hoc text into versioned, reusable, parameterized organizational assets.

Prompt Template Structure:

```yaml
prompt_template:
  id: root_cause_analysis_v2
  version: 2.1.0
  category: investigation
  visibility: organization
  
  system_prompt: |
    You are an expert software debugger analyzing a bug in {{repository}}.
    
    CRITICAL RULES:
    1. Use ONLY the context provided below. Do not guess or imagine code.
    2. Every claim must cite the exact file path and line number from the context.
    3. If you cannot determine the root cause with the provided context, say so clearly.
    4. Do not suggest fixes unless explicitly asked.
  
  user_prompt_template: |
    ## Bug Description
    {{trigger_query}}
    
    ## Relevant Code
    {% for file in step_1.files %}
    ### {{file.path}}
    ```{{file.language}}
    {{file.content}}
    ```
    {% endfor %}
    
    ## Dependency Graph
    {{step_2.dependency_graph | json}}
    
    ## Recent Changes
    {% for commit in step_3.commits %}
    - {{commit.date}}: {{commit.message}} ({{commit.author}})
    {% endfor %}
    
    ## Required Output
    Return a JSON object with:
    {
      "root_cause": "string with exact file:line references",
      "confidence": "high|medium|low",
      "evidence": ["list of specific evidence points"],
      "requires_more_context": boolean,
      "affected_components": ["list of component names"]
    }
  
  variables:
    - name: repository
      type: string
      source: trigger_param
    - name: trigger_query
      type: string
      source: trigger_query
    - name: step_1
      type: object
      source: step_output
    - name: step_2
      type: object
      source: step_output
    - name: step_3
      type: object
      source: step_output
  
  default_llm:
    provider: anthropic
    model: claude-4
    temperature: 0.3
    max_tokens: 4096
  
  output_format: json
  output_schema: {root_cause: string, confidence: string, ...}
```

The template uses Jinja2 syntax for variable interpolation and control flow. It can reference trigger parameters ({{trigger_query}}), step outputs ({{step_1.files}}), and workflow metadata ({{repository}}). It supports conditionals ({% if %}, {% for %}), filters ({{value | json}}), and nested variable drilling ({{step_1.top_result.function_name}}).

Versioning and A/B Testing:

Every template change creates a new version. Workflow runs reference a specific template version, so a running workflow doesn't break when the template is updated. The system tracks which template versions produce the best outcomes (as measured by user feedback, approval rates, and downstream success), enabling data-driven prompt improvement.

Template Rendering:

When a workflow step needs a prompt, the Prompt Engine collects the execution state — all previous step outputs, all trigger parameters, all workflow metadata — and renders the template. The rendered prompt is then passed to the LLM block for execution. This means the LLM never sees the template syntax; it only sees the fully rendered prompt with all variables resolved.

4.6 The LLM Resource Pool: Models as Configurable Resources

The LLM Resource Pool treats language models as configurable, interchangeable resources — like database connections in an application. A workflow doesn't hardcode "use Claude-4." It says "use the model configured for investigation tasks" or "use my preferred model" or "use the cheapest model that meets the quality threshold."

LLM Configuration:

```yaml
llm_config:
  id: claude-4-primary
  provider: anthropic
  model: claude-4
  display_name: "Claude 4 (Primary)"
  api_key_vault_path: /vault/anthropic/primary
  region: us-east
  capabilities:
    max_context_tokens: 128000
    max_output_tokens: 4096
    supports_streaming: true
    supports_function_calling: true
  cost:
    input_per_1k_tokens: 0.015
    output_per_1k_tokens: 0.075
  status: active
  health:
    avg_latency_ms: 850
    error_rate_pct: 0.2
    last_checked: 2024-07-05T09:00:00Z
```

Routing Logic:

When a workflow step requires an LLM, the router resolves which model to use through a chain of decisions:

1. Step override: Does this specific step specify a model? (e.g., "use on-premise model for security analysis")
2. User preference: Does the triggering user have a preference for this workflow type?
3. Team policy: What models are allowed for this team? Are there region constraints?
4. Budget check: Has the user or team exceeded their monthly token budget? If so, route to a cheaper model.
5. Health check: Is the preferred model currently healthy? If not, fail over to the next available model.
6. Fallback chain: If all preferred models are unavailable, use the configured fallback chain.

The router wraps the existing multi-provider LLM client that RIP already uses (core/llm/client.py), so all the existing provider adapters (Ollama, OpenAI, Anthropic, Google, Groq, Azure, OpenRouter) work without modification.

4.7 Organizational Memory: Knowledge That Compounds

The Memory Engine transforms the Gateway from a stateless context provider into a system that gets smarter with every use. Every completed workflow run writes to organizational memory. Every investigation, every decision, every fix becomes searchable, retrievable knowledge for future workflows.

Memory Entry Structure:

```yaml
memory_entry:
  id: mem-2024-0742
  workflow_run_id: run-4821
  type: bug_investigation
  timestamp: 2024-07-05T09:23:00Z
  
  summary: "Payment rounding error caused by Math.floor() in CurrencyConverter.ts:67"
  
  context:
    repository: payment-service
    affected_files: [CurrencyConverter.ts]
    root_cause: "Math.floor used instead of Math.round for regulatory limit check"
    fix_applied: "Changed Math.floor to Math.round on line 67"
    confidence: high
  
  evidence:
    dependency_chain: [transferRoute.ts, paymentHandler.ts, refundService.ts]
    related_commits: [abc123, def456]
    discussion_references: []
  
  decisions:
    - approved_by: priya
      approval_time: 2024-07-05T08:02:00Z
      comment: "Good catch. Merge it."
  
  embedding: [0.123, 0.456, ...]  # Semantic embedding for similarity search
  tags: [bug, payment, rounding, currency, high-priority]
  
  ttl_days: 365
```

Memory Retrieval:

When a new workflow starts, the Context Engine automatically queries organizational memory alongside its other sources. It searches for:

· Past investigations of the same repository or module
· Similar bug descriptions (via semantic embedding similarity)
· Architectural decisions that might constrain the current work
· Past fixes applied to related code
· Onboarding materials created for the affected components

The retrieved memories are injected into the context before the LLM ever sees the request. This means the LLM benefits from the organization's accumulated experience without the developer needing to know what past investigations exist.

The Compounding Effect:

The first time a bug is investigated in the payment service, the memory is empty. The developer and AI work from scratch. But the second time, the memory contains the first investigation. The AI can say: "A similar issue was investigated 3 months ago. The root cause was connection pool exhaustion. Consider checking BankAdapter connection configuration before exploring other hypotheses."

After 100 investigations, the organization has a brain. New developers onboard in days instead of weeks. Bugs that would have taken senior developers hours to diagnose are caught by memory retrieval in minutes. When a senior developer leaves, their knowledge doesn't walk out the door — it's embedded in the organizational memory.

4.8 Session Coordination: Preventing Conflicts Before They Happen

The Session Coordinator solves a problem that every growing team experiences: two developers modifying the same files without knowing about each other.

The existing Gateway already had conflict detection — it could check if two active sessions were touching overlapping files. The Session Coordinator extends this to the workflow level.

How It Works:

Every active workflow run registers with the Session Coordinator. It declares what files it's reading, what files it's modifying, and its estimated completion time. The coordinator maintains a live map of all active sessions and their file footprints.

When a new workflow starts, the coordinator checks for overlaps:

· If both sessions are only reading the same files: no conflict, proceed.
· If one session is modifying and another is reading: low risk, notify both users but proceed.
· If both sessions are modifying the same files: high risk, pause the newer session and notify both users.

The coordinator can suggest resolution strategies:

· Sequential execution: "Let Priya's refactoring finish first (est. 15 minutes), then Rohan's bug fix will automatically rebase on her changes."
· Safe parallelism: "Priya is modifying lines 45-78. Rohan is modifying lines 120-200. These don't overlap. Both can proceed safely."
· Manual resolution: "Both changes touch the same function. Coordinate with each other before proceeding."

This happens before any code is written, not at merge time when conflicts are expensive to resolve.

4.9 The Event Bus: The Nervous System

The Event Bus is the communication backbone of the entire system. Every significant action — a workflow starting, a step completing, an approval being requested, a notification being sent — emits an event on the bus. Other components subscribe to events they care about.

```python
Event:
  id: evt-2024-0742-0001
  type: step_completed | workflow_started | approval_required | ...
  workflow_run_id: run-4821
  step_id: step_4
  source_block_id: llm.analyze
  payload: { ... }
  timestamp: 2024-07-05T09:23:00Z
```

Subscribers:

· Audit Engine subscribes to everything. Every event is persisted to the audit log for compliance and debugging.
· Notification Engine subscribes to user-facing events: approval_required, workflow_completed, workflow_failed. It delivers push notifications, in-app badges, and Slack messages.
· Session Coordinator subscribes to workflow_started to register new sessions for conflict detection.
· Memory Engine subscribes to workflow_completed to save results to organizational memory.
· Usage Tracker subscribes to step_completed to aggregate token usage and cost metrics.
· WebSocket Stream subscribes to events for a specific run, forwarding them to connected clients for live UI updates.

The Event Bus is backed by the existing PostgreSQL infrastructure — no new services required. It absorbs the existing live-pipeline event stream (intent, plan, source_start, source_done, done) that the Gateway already emits, extending it with workflow-level events.

4.10 The Mobile Application: Control Plane in Your Pocket

The mobile app is not a companion. It's not a simplified viewer. It's a first-class control surface that can do everything the desktop can do — trigger workflows, monitor execution, approve actions, resolve conflicts, and even build new workflows.

Chat Interface (Preserved and Enhanced):

The existing chat interface continues to work exactly as before. Developers can type /search, /explain, /trace commands and get responses from RIP and the Gateway. The live pipeline trace (PipelineStepList → PipelineSummaryChip) shows real-time progress of context retrieval.

Workflow Dashboard (New):

A new drawer entry opens the Workflow Dashboard. This shows:

· Active workflows (with live status indicators)
· Pending approvals (with one-tap approve/reject)
· Recent workflow history (with duration, cost, and outcome)
· Quick-action buttons for common workflows (Bug Investigation, Quick Fix, Security Audit)

Workflow Canvas Builder (New — The Killer Feature):

This is the centerpiece of the mobile experience. Users build workflows visually by placing blocks on an infinite canvas and connecting them with wires.

The canvas supports:

· Pan and zoom (pinch gestures)
· Drag blocks from a categorized palette (RIP, GitHub, AI, Tools, Flow)
· Connect blocks by dragging from output ports to input ports
· Tap any block to expand its full configuration
· Live preview during execution (blocks animate, wires show data flow)
· Undo/redo, minimap, zoom-to-fit

A user can build a complete bug investigation workflow — RIP search → dependency trace → GitHub commits → AI analysis → approval gate → PR creation — entirely from their phone, by dragging blocks and connecting wires, without writing a single line of code or YAML.

Trigger by Natural Language:

Saved workflows are triggered by typing a query in natural language. The user opens their "Bug Investigation" workflow, types "transfers over $10k failing with regulatory limit error," and taps Run. The system resolves the query to workflow inputs using the existing Intent Classifier and parameter extraction, then executes the entire workflow.

Approval Interface:

When a workflow hits an approval gate, the approver receives a push notification. Tapping it opens a detailed approval screen showing:

· What the workflow is doing (e.g., "Bug fix for payment rounding error")
· What the AI found (root cause, confidence, evidence)
· What changes are proposed (full diff, affected files, dependency impact)
· Test results (if available)
· One-tap Approve or Reject buttons

The approver can make this decision from anywhere — bed, beach, or bus.

Integration Management:

The existing Integrations screen (OAuth connect, API key entry, project allocation) continues to work. New MCP servers registered here automatically appear in the workflow block palette, with zero additional configuration.

---

BOOK TWO: THE REAL-LIFE STORIES

---

Chapter 5: A Day at FinSecure — The Complete System in Action

5.1 The Organization

FinSecure is a fintech company with 120 developers across three teams. They've been using RIP and the Context Gateway for six months. Here's their setup:

Payment Team (40 developers):

· Builds payment processing, transfers, refunds
· Policy: AI can suggest code but needs human approval for payment code
· Allowed models: Claude (reasoning), GPT (code generation)
· Blocked: Any model sending data outside India
· Senior devs can self-approve; juniors need senior approval for everything

Security Team (15 developers):

· Builds authentication, encryption, fraud detection
· Policy: AI can only analyze, never write code directly
· Allowed models: On-premise model only (nothing leaves the building)
· Every AI action needs security lead approval

Frontend Team (65 developers):

· Builds web app, mobile app, dashboards
· Policy: AI can auto-merge UI changes if tests pass
· Allowed models: Any model; prefer GPT for UI code
· Juniors can auto-merge small UI fixes

The platform team has set up workflows, prompt templates, LLM pools, and approval rules for the entire organization. Every developer has the Gateway mobile app.

5.2 8:00 AM — Priya Approves a Fix From Bed

Priya, a senior developer on the Payment Team, wakes up and checks her phone. She has a Gateway notification:

"Rohan's bug fix needs approval — Payment rounding error — Risk: Medium"

Rohan is a junior developer who started two months ago. Last night, he triggered the "Bug Investigation" workflow with the query: "International transfers over $10,000 showing wrong converted amount."

The workflow ran automatically:

1. RIP searched the payment codebase — found CurrencyConverter.ts as the top result
2. RIP traced all dependencies — found 4 callers across 3 services
3. GitHub found 3 recent commits touching that file
4. AI (Claude-4) analyzed the context and found: Math.floor() should be Math.round() on line 67
5. The approval gate paused the workflow because Rohan is a junior developer

Priya reviews the AI's analysis on her phone. She sees the exact code, the dependency graph, the commit history, and the proposed one-line fix. She taps Approve. The workflow resumes automatically: it creates a PR, assigns reviewers, and notifies Rohan.

Time: 45 seconds. From bed. Before breakfast.

Without the Gateway, this would have required Priya to open her laptop, pull the latest code, manually review the changes, and create the PR herself — a 30-minute interruption to her morning.

5.3 9:30 AM — Rohan Learns From the System

Rohan arrives at the office and sees his PR is already approved and merged. But he doesn't just accept the AI's fix blindly. He opens the workflow trace to understand WHY.

The trace shows every step:

· What RIP found and why those files were ranked highest
· The complete dependency graph showing all callers and callees
· The recent commits that might have introduced the bug
· The exact prompt that was sent to the AI (all 4,200 tokens of it)
· The AI's full response with confidence scores and evidence citations
· Priya's approval with her comment: "Good catch."

Rohan learns three things from this single workflow run:

1. How the payment processing dependency chain works (from the RIP trace)
2. That regulatory limits involve rounding behavior (from the AI analysis)
3. That his team lead trusts AI-assisted fixes when the evidence is clear (from the approval)

This is organizational learning happening in real-time. Next time Rohan sees a similar issue, he'll recognize the pattern immediately.

5.4 11:00 AM — Meera Builds a Security Workflow From Her Phone

Meera is the security lead. Every month, she spends three days manually running security audits on all authentication code. Today, while waiting for a meeting, she builds a workflow to automate this.

She opens the Gateway mobile app, creates a new workflow, and starts adding blocks from the palette:

1. Trigger: Scheduled — first of every month at 2 AM
2. RIP: Find All Auth Code — searches for authentication, tokens, sessions, passwords, encryption
3. RIP: Trace Dependencies — traces everything connected to the auth modules, depth 5
4. Security Scanner — a custom MCP tool her team built, runs static analysis for vulnerabilities
5. GitHub: Dependency Audit — checks all dependency versions for known CVEs
6. AI: Correlate Findings — but locked to the on-premise model (security team policy)
7. Approval Gate — Meera must review before any tickets are created
8. Jira: Auto-Create Tickets — for each confirmed finding, create a ticket assigned to the relevant team lead
9. Notification — post summary to #security-reports Slack channel

She saves it as "Monthly Security Deep Scan" and taps "Test Run" against last month's code. Eight minutes later, she has a complete security report with 3 medium findings and 0 critical issues.

This workflow will now run automatically at 2 AM on the first of every month, forever, without Meera touching it. She'll get a notification to review the findings, approve or reject each one, and the system will create Jira tickets automatically. What used to take three days now takes eight minutes of computer time plus five minutes of Meera's review time.

5.5 2:00 PM — Vikram Investigates From the Beach

Vikram is a senior developer on vacation in Goa. He gets a Slack message: "The refund service is throwing errors in production." He doesn't have his laptop.

He opens the Gateway mobile app, taps "Bug Investigation," and types: "Refund service throwing NullPointerException when processing partial refunds. Started after today's 10 AM deployment."

The workflow runs on the office server. Vikram watches the live progress on his phone:

· ✅ RIP Search (1.2s) — Found RefundService.java and 8 related files
· ✅ RIP Trace (0.8s) — 6 callers, 4 dependencies identified
· ✅ GitHub Commits (1.1s) — Found the 10:03 AM deployment, authored by Rohan
· 🔵 AI Analyzing (running) — Tokens streaming live on screen

Two minutes later, the AI identifies the root cause: Rohan's morning fix changed the return type of a shared function, and the refund service wasn't updated to handle the new type. Vikram can see the exact diff, the dependency chain, and a proposed fix — all from his phone on the beach.

He forwards the analysis to the team chat: "Rohan's morning fix needs a follow-up in RefundService. Gateway found it. Someone please apply the suggested fix." The on-call developer picks it up and resolves the issue within 30 minutes.

Without the Gateway, Vikram would have been unreachable, and the team would have spent hours debugging a production issue without the senior developer who understood both systems.

5.6 3:30 PM — Conflict Prevention in Action

Amit and Sarah, both on the Frontend Team, are working on the dashboard simultaneously. Neither knows about the other.

Amit triggers a workflow: "Add export button to dashboard header."
Sarah triggers a workflow: "Fix chart rendering in dashboard component."

Both workflows start. Both will touch Dashboard.tsx.

The Gateway's Session Coordinator detects this immediately. It analyzes the specific lines each workflow will modify:

· Amit's changes: Lines 12-45 (the header section)
· Sarah's changes: Lines 120-200 (the chart rendering section)

The coordinator determines: These changes do not overlap. Safe to proceed in parallel.

Both Amit and Sarah get a notification: "Another workflow is also touching Dashboard.tsx, but your changes target different sections. No conflict expected. The Gateway will monitor and alert if anything changes."

Both continue working. Both PRs merge without conflict. Without the Gateway, they would have discovered the overlap at merge time, 4 hours later, causing delays and frustration.

5.7 6:00 PM — Karan Onboards in Minutes, Not Weeks

Karan joins the Frontend Team. It's his first day. He needs to understand how dashboard authentication works.

Instead of asking seniors or reading code for days, he opens the Gateway and selects the "Onboarding: Architecture Overview" workflow. He types: "How does dashboard authentication work?"

The workflow runs and returns:

From Organizational Memory (automatically retrieved):

· Amit's investigation from 2 months ago: "Dashboard auth flow traced from login → token → API calls"
· Sarah's bug fix from 1 month ago: "Auth token refresh was broken, fixed in AuthService.ts line 89"
· Architecture decision from 6 months ago: "Chose JWT over session tokens because of mobile app requirements"
· Vikram's onboarding guide: "New developer guide to auth system" (written before he went on vacation)

Live Architecture (from RIP):

· Complete dependency graph from LoginPage.tsx → AuthService.login() → API /auth/token → JWT → SecureStore
· Every API call includes Authorization: Bearer <jwt>
· Token auto-refreshes at 50% expiry

Karan learns in 10 minutes what used to take 2 weeks of asking questions and reading code. The system automatically pulled relevant past investigations, architectural decisions, and even a guide Vikram wrote months ago — all from organizational memory that accumulated naturally as people used the Gateway.

5.8 Night — The System Works While Everyone Sleeps

At 9 PM, the scheduled "Weekly Dead Code Cleanup" workflow runs. RIP scans the entire codebase for unreferenced functions. It finds 23 candidates. The AI verifies each one (checking for reflection, dynamic calls, route handlers). It confirms 18 are truly dead. It creates 3 PRs grouped by module, assigns them to team leads for morning review. Cost: $0.42.

At 11 PM, the "Dependency Health Check" runs. RIP extracts all dependencies, GitHub checks latest versions, AI evaluates update risk. Two critical updates found, five minor ones. PRs created. Security team notified about one dependency with a known CVE. Cost: $0.31.

At 2 AM, Meera's "Monthly Security Deep Scan" runs for the first time. RIP finds all auth code, the custom security scanner runs, AI correlates findings on the on-premise model. Report generated, awaiting Meera's morning approval. Cost: $0 (on-premise model).

Total AI cost for all overnight automation: $0.73. Total developer time saved: approximately 35 hours of manual work.

---

Chapter 6: Complete Technical Reference — Every API, Every Schema

6.1 Full Database Schema

The system's data model captures every aspect of the control plane: workflow definitions, block configurations, wire connections, execution runs, step states, prompt templates, LLM configurations, organizational memory, notifications, and audit logs.

Core Workflow Tables:

workflow_definitions stores the workflow metadata — name, description, category, version, owner, project scope, visibility, canvas state, and run statistics. Each workflow is a container for blocks and wires.

workflow_blocks stores individual blocks within a workflow. Each block has a step identifier (step_1, step_2), a reference to its block type (rip.search, llm.analyze), canvas positioning coordinates, type-specific configuration (as JSONB), input bindings (as JSONB array describing how each input field gets its value), and execution parameters (retry policy, timeout).

workflow_wires stores connections between blocks. Each wire has a source block and port, a target block and port, an optional field-level mapping configuration, and visual properties (color, label). Wires define the data flow and execution dependencies.

workflow_triggers defines how workflows start. Trigger types include manual_query (user types natural language), scheduled (cron expression), webhook (HTTP endpoint), file_watch (filesystem events), and event (internal event bus). Configuration is stored as JSONB specific to each trigger type.

workflow_parameters defines the parameters exposed to the trigger. Each parameter has a name, type, required flag, default value, and optional extraction hint for natural language queries. When a user triggers a workflow with a query like "fix payment bug," the system extracts parameter values from the query text.

workflow_approval_gates defines when and how approval is required. Gates can be unconditional (always), conditional on risk scores, lines changed, or protected paths, or role-based. Configuration specifies who can approve, what evidence is shown, timeout behavior, and notification preferences.

Execution Tables:

workflow_runs stores every execution of a workflow. Each run captures the trigger input, resolved parameters, current status, timing information, token usage and cost, error details, and a complete immutable snapshot of the workflow definition at run time. This snapshot ensures that a run can be replayed or audited even if the workflow definition is later modified.

workflow_run_steps stores the state of each step within a run. Each step record captures the resolved inputs, the output, timing, retry count, LLM-specific metrics (provider, model, tokens, cost, temperature, prompt), tool-specific details, error information, and approval status. The events array stores all events emitted during the step's execution for replay.

Prompt Template Tables:

prompt_templates stores versioned prompt templates. Each template has a system prompt, a user prompt template (with Jinja2 variable syntax), extracted variables, default LLM configuration, output format specification, and usage statistics.

prompt_template_versions stores the version history of each template. Every edit creates a new version with a change description, enabling audit trails and rollback.

Block Registry Table:

block_type_registry stores all available block types — both built-in and dynamically registered from MCP sources. Each entry describes the block's identity, kind, display properties, schemas, capabilities, permissions, and documentation. This table feeds the workflow builder's block palette.

Memory and Notification Tables:

memory_entries stores organizational memory — the accumulated knowledge from completed workflow runs. Each entry has a type, summary, structured context, evidence, decisions, semantic embedding, tags, and TTL.

notifications stores user notifications with delivery tracking across push, in-app, and email channels.

notification_subscriptions stores per-user notification preferences with event type filters, channel preferences, and device tokens for push delivery.

6.2 Complete API Reference

The system exposes a comprehensive REST API under a unified host and authentication model. All endpoints use the same RIP API key for authentication, and all are mounted under the same FastAPI server.

Workflow CRUD API:

POST /gateway/api/workflows — Create a new empty workflow. Accepts name, description, category, project scope, visibility, and canvas state. Returns the workflow ID and the auto-created trigger block ID.

GET /gateway/api/workflows — List workflows for the authenticated user, optionally filtered by project, category, and status. Returns workflow metadata without full block/wire details for efficiency.

GET /gateway/api/workflows/{id} — Get a complete workflow definition including all blocks, wires, triggers, parameters, and approval gates. This is the full load for the canvas editor.

PATCH /gateway/api/workflows/{id} — Update workflow metadata (name, description, canvas state).

DELETE /gateway/api/workflows/{id} — Delete a workflow and all associated blocks, wires, runs, and triggers.

Block CRUD API:

POST /gateway/api/workflows/{id}/blocks — Add a block to the workflow canvas. Accepts block type ID, step ID, canvas position, configuration, and input bindings. Returns the block ID.

GET /gateway/api/workflows/{id}/blocks — List all blocks in a workflow with their current configuration.

GET /gateway/api/workflows/{id}/blocks/{step_id} — Get a single block's full configuration including resolved block type information.

PATCH /gateway/api/workflows/{id}/blocks/{step_id} — Update a block's configuration, position, or input bindings. Supports partial updates.

DELETE /gateway/api/workflows/{id}/blocks/{step_id} — Delete a block and all wires connected to it.

POST /gateway/api/workflows/{id}/blocks/reorder — Update the execution order of blocks (for linear sequences where order matters beyond wire dependencies).

Wire CRUD API:

POST /gateway/api/workflows/{id}/wires — Add a wire between two blocks. Validates that the connection doesn't create a circular dependency. Accepts source and target block IDs with port specifications and optional field mapping.

GET /gateway/api/workflows/{id}/wires — List all wires in a workflow.

DELETE /gateway/api/workflows/{id}/wires/{wire_id} — Delete a wire.

Workflow Execution API:

POST /gateway/api/workflows/{id}/run — Trigger a workflow execution. Accepts a natural language query and optional structured parameters. Returns the run ID and a WebSocket URL for live event streaming.

GET /gateway/api/workflows/{id}/runs — List past runs of a workflow with status, timing, and cost summaries.

GET /gateway/api/workflows/{id}/runs/{run_id} — Get a complete run with all step states, inputs, outputs, and events. This is the full audit trail for a workflow execution.

POST /gateway/api/workflows/{id}/runs/{run_id}/approve — Approve or reject a pending approval gate. Resumes or terminates the workflow.

POST /gateway/api/workflows/{id}/runs/{run_id}/cancel — Cancel a running workflow.

POST /gateway/api/workflows/{id}/runs/{run_id}/answer_missing_input — Provide a value for a step that paused awaiting input, resuming the workflow.

Block Palette API:

GET /gateway/api/blocks/palette — Get available blocks for the workflow builder palette. Supports filtering by category, kind, and search text. Returns blocks grouped by category with usage statistics.

GET /gateway/api/blocks/{block_type_id} — Get detailed information about a specific block type including schemas, documentation, and examples.

Prompt Template API:

POST /gateway/api/prompts — Create a new prompt template. The system automatically extracts variables from the template for documentation.

GET /gateway/api/prompts — List prompt templates for the authenticated user.

GET /gateway/api/prompts/{id} — Get a prompt template with all version history.

POST /gateway/api/prompts/render — Render a prompt template with provided context. Useful for testing templates before using them in workflows.

POST /gateway/api/prompts/validate — Validate a prompt template's syntax and variable references without saving.

LLM Pool API:

GET /gateway/api/llms — List configured LLM providers with health status and cost information.

GET /gateway/api/llms/health — Check health of all configured LLMs with latency measurements.

POST /gateway/api/llms/{id}/test — Test an LLM configuration with a simple prompt to verify connectivity.

Notification API:

POST /gateway/api/notifications/devices — Register a device for push notifications.

GET /gateway/api/notifications — List notifications for the authenticated user with read status.

POST /gateway/api/notifications/{id}/read — Mark a notification as read.

WebSocket Endpoints:

WS /ws/workflows/{run_id} — Stream live workflow execution events. Clients receive events for step start, step completion, step failure, token streaming, approval requests, and workflow completion. This is what powers the live canvas animation during workflow execution.

6.3 Block Implementation Reference

Every block in the system implements the Block interface. Here is how key blocks are implemented:

RIP Search Block (rip.search):

This block wraps the existing RIP search capability. It accepts a query string, repository identifier, and max results count. It calls the RIP source (which may be a CLI subprocess in local mode or an API call in server mode) and returns structured results including files, functions, scores, and a top result. It's tagged as kind retrieval and category RIP. The implementation is a thin adapter over the existing RIP source — no new search logic, just the block contract.

RIP Trace Block (rip.trace):

Wraps RIP's dependency tracing. Accepts a symbol name, repository, depth, and direction (upstream, downstream, or both). Returns callers, callees, a dependency graph structure, and a list of affected files. Used in impact analysis and architectural investigation workflows.

LLM Analyze Block (llm.analyze):

Wraps an LLM call through the LLM Resource Pool router. Accepts a rendered prompt (already processed by the Prompt Engine in a separate step) and configuration (model preference, temperature, max tokens, output format). Routes to the appropriate model based on user/team policy, streams tokens to the event bus for live UI updates, and returns the analysis text plus token usage and cost metrics. Reuses the existing multi-provider LLM client from RIP's core without modification.

Approval Gate Block (approval.gate):

Evaluates whether approval is required based on configured conditions (always, risk threshold, lines changed, protected paths, role-based). If approval is not required, returns immediately with approved: true. If approval is required, creates an approval request in the database, emits an approval_required event (which triggers notifications), and returns suspended — pausing the entire workflow until an external POST /approve call resumes it.

GitHub Create PR Block (github.create_pr):

Wraps the GitHub MCP source's write capabilities. Accepts branch name, PR title, PR description, and reviewer configuration. Creates a branch, commits changes, and opens a pull request. Gated by the Permission Engine — only executes if the triggering user and workflow have write access to the repository.

Terminal Run Tests Block (terminal.run_tests):

A built-in MCP block that executes a sandboxed terminal command. Accepts a command string, working directory, and timeout. Validates the command against an allowlist (only test runners like pytest, npm test, go test are permitted; dangerous commands like rm, sudo, curl are blocked). Returns pass/fail status, stdout, stderr, and exit code.

Notification Block (notification.send):

Emits a notification event on the event bus with the target user and message content. The Notification Engine picks up this event and delivers it through push notification, in-app badge, email, or Slack based on the user's preferences.

---

Chapter 7: Development Roadmap — From Current State to Full Control Plane

7.1 Phase A: Foundation — Event Bus and Block Contract

Goal: Build the infrastructure that everything else sits on. No user-facing changes. All existing features continue working exactly as before.

Deliverables:

· Implement events/bus.py backed by existing PostgreSQL audit infrastructure
· Implement blocks/base.py with the Block, BlockResult, ExecutionContext, and BlockRegistry abstractions
· Wrap the existing Gateway get_context pipeline as a context.retrieve block
· Wrap existing dynamic MCP sources as tool blocks by adding the usable_as field
· Register built-in blocks at startup
· Zero changes to existing API endpoints or behavior

Verification:

· All existing tests pass
· The context.retrieve block produces identical output to the existing /gateway/api/context endpoint
· Block registry correctly lists all built-in and MCP-derived blocks
· Event bus delivers events to subscribers without affecting existing pipeline performance

7.2 Phase B: Workflow Engine MVP and Mobile Builder

Goal: Enable users to create, save, and execute workflows. Ship the mobile block-by-block builder as the primary creation surface.

Deliverables:

· WorkflowDraft and WorkflowRun storage models with Alembic migrations
· Sequential workflow execution (no branching yet) supporting retrieval, prompt, and LLM steps
· Complete Workflow CRUD API (workflows, blocks, wires, triggers, parameters)
· Workflow execution API (run, get status, cancel)
· WebSocket endpoint for live run event streaming
· Mobile canvas builder UI: infinite canvas, drag-drop blocks from palette, wire connections, block detail expansion
· Trigger-by-query: user types natural language, system resolves to workflow inputs
· Two built-in template workflows: Bug Investigation and Architecture Overview
· CLI parity: gateway workflow run <template> --params ...

Verification:

· User can create a workflow on mobile by dragging blocks and connecting wires
· User can trigger the workflow with a natural language query
· Workflow executes all steps in order and returns results
· Live trace shows step-by-step progress in the mobile app
· Existing chat interface continues to work unchanged
· Workflow runs are persisted and replayable

7.3 Phase C: Prompt Engine and LLM Resource Pool

Goal: Externalize prompts from code into versioned templates. Make LLM selection policy-driven rather than hardcoded.

Deliverables:

· Prompt Engine with Jinja2 rendering, variable extraction, and versioning
· Prompt Template CRUD API (create, list, get, render, validate)
· Migration of existing inline prompts to seed templates
· LLM Resource Pool with named configurations, health tracking, and routing logic
· LLM Pool API (list, health check, test)
· Integration with Workflow Engine: prompt block type that renders templates, llm block type that routes through the pool
· Prompt version history and usage statistics

Verification:

· Existing prompts produce identical output when rendered through the Prompt Engine
· LLM routing correctly applies user preferences, team policies, and health-based failover
· Prompt templates can be edited and versioned without breaking running workflows
· A/B comparison shows metrics for different prompt versions

7.4 Phase D: Approval Gates and Verification

Goal: Enable workflows that pause for human review and workflows that validate their own output.

Deliverables:

· Approval gate block implementation with condition evaluation and suspension
· Approval API (approve/reject) and mobile approval interface
· Notification integration: push notifications for pending approvals
· Terminal block for running tests and linters in a sandboxed environment
· Allowlist-based command policy
· Integration: approval gates can consume verification results to inform approvers
· Timeout handling for abandoned approvals

Verification:

· Workflow pauses at approval gate and notifies approver
· Approver can approve or reject from mobile with full context
· Rejected workflows stop and record the rejection reason
· Terminal block executes allowed commands and blocks dangerous ones
· Test results appear in approval context

7.5 Phase E: Deployment Blocks and Organizational Memory

Goal: Enable workflows that create PRs, merge code, and deploy. Enable knowledge accumulation across workflow runs.

Deliverables:

· GitHub write-mode blocks: create branch, commit changes, create PR, request reviewers
· Deployment blocks gated by Policy Engine repository protection levels
· Memory Engine: save completed workflow results as searchable memory entries
· Memory retrieval block: automatically query organizational memory during context assembly
· Semantic embedding of memory entries for similarity search
· TTL-based memory expiration

Verification:

· Workflow creates a real PR on GitHub with auto-generated description
· Memory entries are created on workflow completion and retrievable in future runs
· Memory search returns relevant past investigations for similar queries
· Deployment blocks respect repository protection policies

7.6 Phase F: Notifications, Usage Tracking, and Plugin Manager

Goal: Complete the mobile experience with push notifications. Give users visibility into their AI usage. Enable third-party block registration.

Deliverables:

· Notification Engine subscribing to event bus for user-facing events
· Push notification delivery via Firebase Cloud Messaging and Apple Push Notification Service
· In-app notification center with read/unread state
· Usage Tracker: token consumption and cost aggregation per workflow run
· Metrics API and dashboard showing personal AI usage
· Plugin Manager: block.json manifest format, install/validate/enable flow
· Composite block creation: group existing blocks into reusable composite blocks

Verification:

· Push notifications delivered within 5 seconds of approval required event
· Usage dashboard shows accurate per-workflow and per-model cost breakdown
· Third-party block can be installed from a manifest and appears in the palette
· Composite blocks can be created, saved, and reused across workflows

7.7 Phase G: Advanced Flow Control and Web Dashboard

Goal: Support branching, loops, and parallel execution. Provide a desktop-grade workflow designer.

Deliverables:

· Conditional branching: condition block type with if/else routing
· Loop blocks: iterate over arrays from previous step outputs
· Parallel execution: steps with no mutual dependencies execute simultaneously
· Web dashboard with full-featured workflow designer canvas
· Drag-and-drop block placement, wire drawing, property panel
· Template gallery with preview, clone, and customize
· Workflow import/export as JSON/YAML

Verification:

· Conditional workflows correctly route based on runtime data
· Parallel steps execute simultaneously and correctly synchronize
· Web designer produces valid workflow definitions consumable by mobile and API
· Exported workflows can be imported and executed without modification

---

Chapter 8: The Vision Realized

8.1 What We Built

We started with a problem: understanding large codebases is the biggest bottleneck in software development. AI coding assistants help write code faster, but they struggle to understand existing systems. Organizations adopting multiple AI tools face chaos — duplicated context, no shared memory, no governance, no coordination.

We built two systems that work together as one platform.

RIP (Repository Intelligence Platform) transforms source code into a queryable knowledge graph. It understands architecture, not just text. It can trace dependencies, analyze impact, detect dead code, generate architecture diagrams, and onboard new developers — all grounded in the actual codebase, not AI hallucination.

Context Gateway evolved from a context optimization pipeline into a complete control plane for AI-assisted software engineering. It now includes:

· Workflow Engine: Executes multi-step, DAG-based workflows with tool execution, AI analysis, human approval, and automated actions
· Block Architecture: Every capability is a composable block — RIP queries, LLM calls, GitHub operations, test execution, notifications, memory operations
· Prompt Engine: Versioned, reusable prompt templates that become organizational assets
· LLM Resource Pool: Policy-driven routing across multiple AI models with health monitoring and failover
· Organizational Memory: Every completed workflow becomes searchable knowledge that compounds over time
· Session Coordination: Proactive conflict detection before code is written
· Mobile Control Plane: Full workflow creation, triggering, monitoring, and approval from a phone
· Event Bus: Everything is observable, auditable, and extensible

8.2 What This Means for Developers

A developer no longer writes lengthy prompts to AI assistants. They trigger workflows — predefined, tested, approved sequences that handle the entire engineering task from context gathering to code generation to testing to PR creation.

A developer no longer spends days tracing dependencies manually. RIP provides the complete architectural picture in seconds, with evidence from the actual code.

A developer no longer loses knowledge when colleagues leave. Organizational memory captures every investigation, every decision, every fix — and surfaces them automatically when relevant.

A developer no longer discovers merge conflicts at merge time. The Session Coordinator warns them before they start typing.

A developer can investigate production issues from the beach. Approve changes from bed. Build workflows while waiting for coffee. The control plane is always in their pocket.

8.3 What This Means for Organizations

An organization no longer fears AI coding tools. The Gateway provides complete governance: permissions, approval chains, audit trails, and policy enforcement. Regulated industries can finally adopt AI-assisted development with confidence.

An organization no longer bets on a single AI vendor. The LLM Resource Pool makes models interchangeable. Swap Claude for GPT for Gemini without changing a single workflow.

An organization no longer loses institutional knowledge. The Memory Engine compounds experience. Every bug fix makes future bug fixes faster. Every architectural decision informs future decisions.

An organization no longer has chaos as multiple AI agents operate simultaneously. The Session Coordinator orchestrates them. The Event Bus makes everything visible. The Audit Engine makes everything accountable.

8.4 The Final Word

This is not an AI coding assistant. This is infrastructure for how organizations build software with AI — today, tomorrow, and as models evolve.

RIP is the eyes that understand the code.
The Gateway is the brain that governs the work.
Together, they form the control plane for AI software engineering.

End of Documentation