# RIP Agent Integration Theory
## How Repository Intelligence Platform Connects to Claude Code, Codex, and the Context Gateway

---

## Table of Contents

1. [Connecting RIP to Claude Code and Codex](#1-connecting-rip-to-claude-code-and-codex)
2. [RIP + Context Gateway + MCP — The Complete Theory](#2-rip--context-gateway--mcp--the-complete-theory)

---

# 1. Connecting RIP to Claude Code and Codex

## The Fundamental Problem RIP Solves for Agents

When you run `claude "add retry logic to the checkout service"` today, Claude Code does one of two things:

1. Reads every file it can find until context fills up — wastes tokens on irrelevant code
2. Works only on the file you have open — misses dependencies entirely

What it actually needs is: *"Here are the 6 files that matter for checkout, here is the call chain, here is where existing retry logic lives in the codebase, here is what breaks if you touch PaymentService."* That is exactly what RIP can produce in milliseconds from its graph and vector index.

---

## Connection Mechanism 1 — MCP Server (the right long-term answer)

Both Claude Code and Codex support the Model Context Protocol. This is the cleanest integration. You expose RIP as an MCP server — a lightweight process that responds to tool call requests from the agent.

The agent calls tools like `rip_trace`, `rip_impact`, `rip_search`, `rip_explain`. RIP answers from its graph and vector index. The agent decides which tools to call, when, and what to do with the results.

From the agent's perspective, RIP looks like a set of tools it can invoke just like it invokes a file read or a bash command. The difference is that one RIP tool call returns pre-digested architectural knowledge that would otherwise cost 50,000 tokens of raw file reading.

The MCP server itself is thin — it is just a protocol adapter sitting in front of the same `core/` engine. No new intelligence, just a new interface.

---

## Connection Mechanism 2 — Context Injection via Hooks

Claude Code has a hooks system. Before the agent runs, you can inject content into its context window. RIP intercepts the agent invocation, classifies the intent of the user's prompt, runs the relevant graph and search queries, assembles a compact context package, and prepends it to whatever the agent was going to receive.

For example: user says `claude "fix the auth bug"`. RIP detects the keyword "auth", runs `repo trace auth`, `repo search "authentication"`, fetches the top 5 relevant files from its index. It prepends a structured summary — call chain, relevant files with line ranges, related tests — into Claude Code's context before the agent even starts thinking. The agent now has surgical context instead of nothing.

This works without any changes to Claude Code itself. It is a wrapper. The downside is it is less dynamic — the context is assembled once upfront rather than the agent being able to ask follow-up questions to RIP mid-task.

---

## Connection Mechanism 3 — `CLAUDE.md` and `.claude/` Context Files

Claude Code reads `CLAUDE.md` at the repo root and `.claude/` directory files as persistent context. RIP can generate and keep these files up to date automatically.

Every time RIP indexes or re-indexes, it writes a fresh `CLAUDE.md` containing: the architecture overview, the critical service map, the entry points, the riskiest modules, the ownership map, the key patterns used in this codebase. Claude Code reads this on every invocation without being asked.

This is the lowest-tech integration but surprisingly powerful. A well-written `CLAUDE.md` generated from actual graph data is worth more than a stale hand-written one. RIP can also write `.claude/architecture.md`, `.claude/dependencies.md`, `.claude/patterns.md` as separate focused documents the agent pulls based on the task.

---

## Connection Mechanism 4 — Pre-task Context Assembly (the "Briefing" Pattern)

Before handing a task to Claude Code or Codex, RIP runs a briefing phase. It takes the user's natural language task, extracts the intent and the symbols mentioned, queries the graph for the relevant subgraph, assembles a token-budgeted context package, and either injects it directly or saves it to a temp file that gets included.

The briefing package looks like this in practice:

- Task description
- Relevant files with their key functions listed
- The call chain for the entry points involved
- A list of files that will be affected by the likely change
- Existing patterns in the codebase for the type of change requested (e.g. "here is how retry logic is implemented in three other services")
- The test files that cover the relevant code

This briefing costs maybe 3,000–5,000 tokens total but replaces what would otherwise be 40,000–80,000 tokens of the agent reading files itself. The agent works faster, stays within context limits on large repos, and makes changes that are architecturally consistent because it understands the existing patterns.

---

## Connection Mechanism 5 — Post-task Impact Validation

This is the reverse direction. After Claude Code or Codex produces a patch, before it is applied, RIP runs an impact analysis on the proposed changes. It checks:

- Which nodes in the graph are touched by the diff
- Which downstream services depend on those nodes
- Whether the patch introduces any new dependencies that conflict with existing architecture
- Whether the changed functions are covered by tests

RIP returns a validation report: *"this change affects 3 downstream services, 2 of which have no tests covering this path, and it introduces a new dependency on CacheService which creates a circular dependency with UserService."* The agent can then revise the patch or the human can make an informed decision.

This turns RIP from a passive context supplier into an active quality gate.

---

## Why This Matters for Token Economics Specifically

A typical 200k LOC repo has around 15,000–25,000 tokens of truly relevant code for any given task. The problem is the agent does not know which 15,000 tokens those are, so it reads much more and still misses things.

RIP knows exactly which 15,000 tokens are relevant because it has the dependency graph. It can produce a context package that is:

- **Complete** — no missing dependencies the agent will discover halfway through the task
- **Minimal** — no irrelevant files wasting the context window
- **Structured** — graph relationships explicit so the agent does not have to infer them
- **Budgeted** — RIP knows the agent's context window size and fills it optimally, prioritizing by relevance score

A Claude Code session that would normally exhaust a 200k token context window on a large repo instead uses 8,000–12,000 tokens for the same task because RIP did the retrieval work upfront. This is not a marginal improvement — it is the difference between the agent being able to handle the task at all versus hitting limits.

---

## The Right Mental Model

Think of RIP as the **senior engineer who briefs the junior contractor before they start work**. Claude Code and Codex are the contractors — fast, capable, but they need to be told what exists before they can work effectively. Without the briefing they either ask naive questions (wasting tokens on file reads) or make changes that break things they did not know existed.

RIP provides the briefing. The contractors do the work. The combination is significantly more capable than either alone.

The MCP integration is the cleanest version of this. Phase 2 of the platform — the Context Gateway — is essentially this briefing system built out into a full orchestration layer. Phase 1 (RIP) builds the knowledge. Phase 2 delivers it to the agents at the right time in the right format.

---

---

# 2. RIP + Context Gateway + MCP — The Complete Theory

This is where the two projects stop being separate tools and become one coherent platform. Understanding how they combine requires understanding what each one lacks alone.

---

## What Each Piece Is Missing Alone

**RIP alone** knows everything about the codebase. It can trace flows, score risk, find dead code, explain architecture. But it is passive. It waits to be asked. It has no concept of *when* to surface knowledge, *how much* to give, *to whom*, or *which agent* needs what right now. It is a library with no librarian.

**Claude Code / Codex alone** can reason and generate. But they go in blind on large codebases. They also have no memory across sessions, no awareness of other agents working simultaneously, and no governance over which tools they call or how many tokens they consume.

**MCP alone** is just a protocol. It defines how agents discover and call tools. It does not decide which tools are appropriate for a given task, does not rank or compress results, does not enforce budgets, does not manage permissions. It is a pipe with no intelligence about what flows through it.

**The Context Gateway** is the missing piece. It is the librarian, the traffic controller, the budget manager, and the quality gate — all sitting between the agents and everything they consume.

---

## How the Three Combine Into One System

The mental model is a three-layer stack:

**Layer 1 — Knowledge (RIP)**
Knows the codebase. Structural graph, semantic vectors, git history, ownership, risk scores. Answers questions about what exists and how things relate.

**Layer 2 — Orchestration (Context Gateway)**
Decides what knowledge to fetch, from which sources, in what order, at what cost, for which agent, under which permissions. Packages and delivers context optimally.

**Layer 3 — Execution (Claude Code / Codex via MCP)**
Receives a perfectly assembled context package. Reasons over it. Generates a patch, explanation, or analysis. Returns output back through the gateway.

The gateway never generates. RIP never orchestrates. The agents never retrieve. Each layer does exactly one thing.

---

## What the Context Gateway Actually Does in This Stack

The gateway is not a proxy that blindly forwards requests. It is an active decision-making layer. When an agent makes a tool call, the gateway intercepts it and does five things before anything reaches RIP or any other tool:

**Intent classification** — it reads the agent's current task and the tool call being made and decides what type of query this is. A trace query needs different context than a search query. A pre-change impact check needs different depth than an explanation request. The gateway routes each request to the appropriate RIP analysis engine rather than letting the agent call RIP directly with raw parameters.

**Multi-source planning** — for a given task, the gateway determines that the agent needs context from RIP (codebase structure), plus possibly from GitHub (open PRs touching the same files), plus from Jira (the ticket this task is implementing), plus from Slack (any discussions about the affected service). It plans which sources to query, in what order, with what priority. RIP is always the primary source for codebase knowledge but it is rarely sufficient alone.

**Token budgeting** — the gateway knows the agent's remaining context window. It allocates that budget across sources. If the model has 40,000 tokens left, the gateway might allocate:

| Source | Token allocation | Reason |
|---|---|---|
| RIP graph results | 18,000 | Primary knowledge source |
| RIP code snippets (vector) | 10,000 | Exact code references |
| GitHub PR context | 6,000 | Related open work |
| Jira ticket | 4,000 | Task requirements |
| Reserve | 2,000 | Agent output headroom |

RIP returns whatever it returns — the gateway compresses and trims it to fit the allocation. The agent never hits a context limit because the gateway enforces the budget before delivery.

**Context ranking and compression** — raw RIP output for a complex trace query might be 30,000 tokens of graph data. The gateway ranks nodes by relevance to the specific task, keeps the highest-scoring ones, summarizes or drops the rest. It transforms a complete but verbose RIP response into a surgical context package. The structural accuracy comes from RIP. The conciseness comes from the gateway.

**Permission filtering** — not every agent gets the same context. A junior developer's AI session should not receive production secrets, deployment credentials, or sensitive architectural details. A senior engineer's session gets full graph traversal depth and production log access. The gateway enforces this per session, per role, per project — before anything leaves RIP.

---

## The MCP Layer — How It Connects Everything

MCP is the protocol that makes this composable. The Context Gateway exposes itself as an MCP server to the agents. RIP exposes itself as an MCP server to the Context Gateway. Other tools — GitHub, Jira, Slack, databases — also expose themselves as MCP servers to the Context Gateway.

This creates a two-tier MCP topology:

**Tier 1 — Agent to Gateway**

Claude Code and Codex see the gateway as a single MCP server with a clean, high-level tool set. Tools like `get_task_context`, `validate_change`, `search_codebase`, `explain_architecture`. The agent does not know or care that the gateway is orchestrating multiple sources behind the scenes. It makes one tool call and receives one perfectly assembled response.

**Tier 2 — Gateway to Sources**

The gateway is itself an MCP client talking to multiple MCP servers — RIP, GitHub MCP, Jira MCP, Slack MCP, and any future tool. It orchestrates these in parallel, merges results, applies budget and permission rules, and returns the assembled package to the agent.

This topology means the agent's tool surface stays simple and stable even as the backend grows. You can add a new data source to the gateway without changing a single line of the agent's tool calls. The agent always talks to one interface. Complexity is hidden in the gateway where it belongs.

---

## Session Memory and Cross-Agent Awareness

This is where the combined system becomes genuinely powerful in ways neither piece achieves alone.

The Context Gateway maintains a memory layer that persists across agent sessions. When Claude Code works on the checkout service today, the gateway records which RIP nodes were accessed, which files were modified, which patterns were used, what the agent's final output was. Tomorrow, when a different agent or the same developer starts a related task, the gateway pre-loads that session context without being asked.

More importantly, the gateway is aware of all active agent sessions simultaneously. If two developers are running Claude Code sessions in parallel and both are about to modify PaymentService, the gateway detects the conflict, surfaces it to both sessions as a warning, and can suggest coordination. RIP provides the knowledge that both sessions are touching the same graph nodes. The gateway provides the awareness that this is happening concurrently.

This cross-agent awareness is impossible when agents talk directly to tools. It only exists because all sessions flow through one orchestration layer.

---

## The Feedback Loop — Agents Improving RIP

The connection is not one-way. As agents use the system, the gateway observes patterns and feeds them back to RIP.

When Claude Code consistently navigates from `AuthController` to `JwtProvider` to `UserRepository` when working on auth tasks, the gateway records that traversal pattern. RIP learns that these three nodes are deeply related for auth tasks even if the graph edges do not make it fully obvious. Future context assembly for auth-related tasks pre-loads these nodes together.

When an agent's patch causes a downstream test to fail that RIP's impact analysis did not predict, the gateway records the miss and adjusts the impact analysis weights for that part of the graph. RIP's graph is always structurally accurate but the relevance scoring improves over time through usage.

This is a learning system. It starts accurate because of RIP's static analysis. It becomes more accurate over time because the gateway observes real agent behavior and real outcomes.

---

## The Compound Effect on Token Economics

The token savings compound at each layer:

| Layer | What it eliminates | Reduction factor |
|---|---|---|
| RIP alone | Agent reading irrelevant files | ~10x fewer tokens on retrieval |
| Context Gateway on top of RIP | Verbose output compressed to budget | ~3x further reduction |
| MCP tier | Redundant tool calls, overlapping results | ~2x further reduction |
| **Combined** | **Agent doing its own retrieval on large repo** | **~60x total reduction** |

An agent that would exhaust a 200k token context window doing its own retrieval on a large repo now completes the same task using 8,000–15,000 tokens. That is not a marginal efficiency gain. It is the difference between the agent being able to handle enterprise codebases at all versus failing on them.

---

## Why This Is the Correct Architecture for the AI Tooling Era

The software industry is converging on a pattern: **small, expert agents orchestrated by intelligent middleware** rather than one massive agent trying to do everything. Claude Code and Codex are the expert agents — they are excellent at their specific task. RIP is the domain expert — it knows the codebase better than any agent can from a context window. The Context Gateway is the orchestration intelligence — it knows which expert to ask, when, and how to combine their outputs.

This is not a novel pattern. It is how mature software systems are built — specialized components with clean interfaces, orchestrated by a layer that understands the whole. What is new is applying it to AI agent infrastructure.

| Component | What it provides |
|---|---|
| RIP | Memory of the codebase |
| Context Gateway | Wisdom about how to use that memory |
| MCP | Common language for everything to communicate through |
| Claude Code / Codex | Execution — reasoning and generation |

Together they make Claude Code and Codex capable of working on systems that are currently too large and complex for them to handle effectively.

---

## Summary — The Build Sequence

```
Phase 1 — Build the memory
  └── Repository Intelligence Platform (RIP)
        Parser → Graph → Vector Search → Analysis Engines → LLM Explanation

Phase 2 — Build the wisdom
  └── Context Gateway + MCP Server
        Intent Classification → Multi-source Planning → Token Budgeting
        → Context Ranking → Permission Filtering → Session Memory

Phase 3 — Connect the agents
  └── MCP integrations for Claude Code, Codex
        Tier 1: Agent ↔ Gateway (high-level tools)
        Tier 2: Gateway ↔ RIP + GitHub + Jira + Slack (source tools)
```

Phase 1 builds the knowledge. Phase 2 builds the orchestration. Phase 3 connects the execution. The platform is only complete when all three exist — but each phase is independently useful and shippable.

---

*Document version: 1.0*
*Covers: RIP → Claude Code/Codex integration theory + RIP + Context Gateway + MCP complete theory*
