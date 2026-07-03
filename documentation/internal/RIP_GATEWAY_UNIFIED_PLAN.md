# RIP + Context Gateway — Unified Product & Mobile Redesign Plan

## 0. What's wrong with the current plan

The existing audit (`Context Gateway → Mobile App: Feature Audit & Integration Plan`) treats RIP and Context Gateway as two backends the phone talks to separately:

- RIP server on `:8000`, Gateway server on `:8001` — two hosts, two health checks, two API keys.
- Tier 3 of the old plan even splits Settings into **"RIP Server"** and **"Gateway Server"** sections, and proposes a **"Gateway Dashboard" home tab** that sits next to (not inside) the existing chat.
- That design asks the user to configure a second server before Gateway features light up, and it visually tells them "this is a second product bolted onto RIP."

Two problems to fix, in order:

1. **One connection, not two.** The app should only ever ask for one Server URL and one API key. Gateway must stop being a second thing the phone connects to.
2. **One product, not two.** Nothing in the UI should say "Gateway" as if it were a separate app. RIP is the whole product. "Repo intelligence" and "orchestration/session/team/token" are just two capability groups inside it.

Everything below re-derives the mobile plan from those two fixes.

---

## 1. Architectural fix: mount Gateway inside RIP's server, not beside it

**Recommended approach — Gateway-as-router, not Gateway-as-service:**

Instead of running `gateway/` as its own FastAPI process on `:8001`, mount its routers into the same FastAPI app that `repo serve` already runs on `:8000`, under an internal prefix (e.g. `/orchestrate/*` or `/gateway/*` — path only, never surfaced in UI copy). Concretely:

- `server/app.py` (RIP) imports and includes Gateway's `context`, `sessions`, `sources`, `metrics`, `feedback`, `audit` routers the same way it already includes `trace`, `impact`, `search`, `git`, `projects`.
- Gateway's MCP tool handlers stay separate (agents connect to MCP directly, not through the phone), but the **REST surface** Gateway exposes becomes just more routes on RIP's existing app.
- Auth is unified for free: RIP's `server/middleware/auth.py` (`RIP_API_KEYS` + the production `api_keys` table) already protects every route on that app — Gateway's routes inherit it automatically instead of needing their own auth story.
- Gateway keeps its own internal services, planner, ranker, session store, etc. — none of that internal architecture changes. Only the **outward-facing port and auth boundary** collapses into RIP's.
- Postgres is already shared between RIP and Gateway per the existing integration checkpoint, so session/audit/feedback tables living in the same DB as RIP's project tables is not new — it's already true today.

**Fallback approach (if merging processes is out of scope right now):** run RIP and Gateway as two processes behind one reverse proxy (Caddy/nginx) on one external port, with the proxy forwarding `Authorization` unchanged and Gateway trusting the same key set. This gets you "one connection" without a code merge, at the cost of running two processes. Prefer the mount-in approach above when possible — it also removes an entire deployment surface (one fewer service to keep alive, one fewer thing to explain in docs).

**Mobile-side consequence:** `SetupScreen` keeps exactly one Server URL field and one API key field. There is no second server section anywhere in Settings. Every Gateway-powered feature described below rides on the same `RipClient` / same base URL the app already uses for search, trace, explain, and indexing.

---

## 2. Product framing: one brand, two capability groups

Don't introduce "Gateway" as a UI concept. Internally the codebase can keep the name; externally, nothing in the app should read like a second product.

| Capability group | What it does | Where the user already knows this from |
|---|---|---|
| **Repo intelligence** (RIP core) | Parses code, builds the graph, indexes semantically, answers "what calls this / what breaks if I change this / what does this file depend on." | Already the whole app today. |
| **Orchestration** (Gateway internals) | Decides *which* sources to query and in what order, tracks *who else* is working in the same repo right now, manages the *token budget* spent per answer, remembers *sessions*, and *learns* from feedback over time. | New, but should feel like RIP getting smarter — not like a second app appearing. |

Every screen and every response in the phone should look like it comes from one assistant that happens to (a) know your code and (b) manage its own retrieval budget and team awareness responsibly. The rule of thumb for every future screen: **if it can't be explained as "RIP being transparent about how it worked," it doesn't get its own tab.**

---

## 3. Full feature list Context Gateway will give to mobile

Same evidence-based categorization as the original audit (A = real and reachable, B = built but needs a small endpoint, C = stub/gap), kept honest — nothing here is upgraded to "ready" just because the two servers are merging. Merging the connection doesn't fix backend stubs; it only fixes how many things the phone has to dial.

| # | Feature | Status | What it needs before mobile can use it |
|---|---|---|---|
| 1 | **Intent classification** (bug_fix / feature / refactor / arch question / investigation / docs + domain + confidence) shown per response | A | Nothing — already in `get_context` payload |
| 2 | **Token budget breakdown** ("7,200 → RIP, 2,400 → GitHub, 2,400 reserve") shown under each response | A/B | Small response-shape addition: per-source `token_allocation`, not just the total |
| 3 | **Source health strip** (RIP always-on, GitHub/Jira/Slack toggleable, live status) | A (except RIP toggle) | RIP's "always-on" state needs to be an explicit field, not an implicit gap |
| 4 | **Circuit breaker status** ("paused until 14:32 after repeated failures") | A | Nothing — already part of source health |
| 5 | **Ranking transparency** ("why item X outranked item Y" — semantic/centrality/recency/pattern/authority) | B | Structured per-item score export (currently only prose) |
| 6 | **Sessions / active work awareness** (who else — or what other agent session — is touching this repo right now) | A | Nothing — `GET /api/sessions/` already returns real data |
| 7 | **Conflict detection** (two active sessions editing the same file) | A | Nothing — computed automatically on every `get_context` call |
| 8 | **Role-based filtering** (junior_dev / developer / senior_dev / ci_agent see different amounts of context) | A (server-enforced) | Nothing to build except *showing the current role* |
| 9 | **Audit trail** (who accessed what, filtered how, when) | B | New `GET /api/audit` list endpoint (writes already persist to Postgres) |
| 10 | **MCP config export** (for connecting Claude Code / Cursor / Codex to this same server) | A | Nothing — same JSON `gateway mcp config` already produces |
| 11 | **Live metrics** (active sessions, tokens delivered, source health snapshot, conflict count) | C — stub | Backend must replace placeholder constants with real aggregation |
| 12 | **Feedback loop** (thumbs up/down + "missing something" / "irrelevant" tags feeding the ranker's learned weights) | B | New `POST /api/feedback` endpoint |
| 13 | **Team/session identity** (if the phone should show "whose" session something is, not just "agent type") | Open question | Sessions currently store `agent_type`, not a human identity — decide before building the Activity screen (see §7) |

Nothing on this list is new versus the original audit — it's the same ground truth. What changes is *how it's presented*, covered next.

---

## 4. Redesigned mobile information architecture

The old plan's mistake was giving orchestration features their own real estate (a "Gateway Dashboard" home tab, a separate Sessions screen, a separate Sources screen, a separate Settings section). The fix: fold every orchestration feature into a surface the user is already looking at.

### 4.1 Chat stays the one screen that matters
No new home tab. Every Gateway-powered signal attaches to the response that's already on screen:

- **Inline intent badge** under each response — tap to expand into the one-line "why" (feature #1).
- **Inline token strip**, collapsed by default, one tap to expand into the per-source bar (feature #2).
- **Inline feedback row** (thumbs + "missing" / "irrelevant" chips) under every response once the endpoint exists (feature #12).
- **Inline conflict banner**, shown *in the conversation* the moment a conflict is detected, not on a separate screen someone has to remember to check (feature #7) — this is the single highest-trust moment in the whole product; it should interrupt the chat, not wait in a tab.
- **Inline ranking breakdown**, tap-to-expand under the "why this was included" affordance once structured scores exist (feature #5).

### 4.2 One "Activity" surface (replaces "Sessions & Team Activity" + part of the old Dashboard)
A single screen, reached from the existing drawer, not a new tab:
- List of sessions on this server (yours and others sharing it) — same data as before, same screen concept as the old plan's #2, just not positioned as a separate "Gateway" feature. It's framed as "what's happening on this repo right now."
- Conflict history lives here too, alongside the live inline banner.

### 4.3 One "Sources" settings screen (replaces separate Gateway Sources + RIP status)
- RIP: always-on badge, health, last query latency — this already exists conceptually as "is my repo indexed."
- GitHub / Jira / Slack: toggle, connection status, circuit breaker state, credential form.
- This screen answers "what does RIP look at when it answers me," whether the source is the code graph itself or an external tool. One list, not two systems.

### 4.4 One Settings screen (replaces "RIP Server" + "Gateway Server" split)
- **Connection**: one Server URL, one API key, one "Test Connection" button. (This is the whole point of §1 — there is nothing else to configure here.)
- **Role**: default role for this device (junior_dev/developer/senior_dev/ci_agent) — this is the one genuinely new field, and it's a single dropdown, not a second server identity.
- **App**: theme, chat history management, notification prefs — unchanged from the original plan.
- Multi-server profiles (old Tier 3 §12) still make sense for someone juggling two *RIP* deployments (e.g. work + personal) — but now that's "switch which RIP server," a single concept, not "switch which RIP+Gateway pair."

### 4.5 Audit log viewer
Kept as a role-gated screen (senior_dev/ci_agent only) reached from Settings or the Activity screen — not a top-level tab, since most users will never open it. Still goes through the same permission engine as everything else (§ "what not to build" from the original audit still applies: never expose raw unfiltered rows).

### 4.6 MCP config export
Unchanged in function, but now doubly simple to explain: it's exporting config for *this one server the phone is already connected to* — no ambiguity about "which of the two servers does this config point at."

---

## 5. Backend prerequisites (Tier 0), redesigned

Original Tier 0 kept, with the connection-unification work added as the first, highest-priority item — it blocks the *framing* of every other item, not just one feature:

```
Tier 0 — Backend (blocking, do first)
  [ ] Mount Gateway's REST routers into RIP's FastAPI app (server/app.py) under one
      internal prefix, sharing RIP's existing auth middleware and API-key store —
      OR stand up a single reverse proxy in front of both processes if a full
      process merge isn't feasible yet. Either way: one external host:port, one
      API key system, verified by hitting every current Gateway route through
      RIP's port before anything else in this list starts.
  [ ] Confirm Gateway's session/audit/feedback tables live in the same Postgres
      instance RIP already uses (already true per the RIP-Gateway integration
      checkpoint — just needs re-verification after the mount).
  [ ] Replace GET /metrics (or /api/metrics under the new mount) stub with real
      aggregation: active session count, total tokens retrieved/delivered,
      per-source health snapshot, active conflict count.
  [ ] Add GET /audit (or equivalent) to list persisted audit log entries with
      filtering by session/role/date.
  [ ] Add POST /feedback accepting session_id, rating, was_helpful,
      missing_context, irrelevant_context.
  [ ] Extend get_context's response shape to include a token_allocation
      breakdown by source, and a simplified per-item score summary for the top
      N included items.
  [ ] Fix validate_change to resolve a diff to affected symbols before calling
      impact, instead of passing the diff straight through.
  [ ] Make RIP's always-on source status an explicit field in the sources
      response instead of an implicit gap.
  [ ] Decide the session-identity question (agent_type vs. human identity) —
      see §7 — before building the Activity screen's "whose session" framing.
```

None of Tier 1 below should be built against a server that still requires two connections — that's the one non-negotiable gate, since it's the thing this whole redesign exists to fix.

---

## 6. Mobile build tiers, redesigned

### Tier 1 — ship once the single-connection backend lands (data already real)
- Inline intent badge + expandable "why" in chat (feature #1)
- Inline token strip in chat, total now / per-source once the response-shape addition lands (feature #2)
- Sources settings screen — RIP + GitHub/Jira/Slack, one list (feature #3, #4)
- Activity screen — sessions + conflict history (feature #6)
- Inline conflict banner in chat (feature #7)
- Settings screen — single connection + role field (no second server section, ever)
- MCP config export screen

### Tier 2 — ship once the two remaining endpoints land
- Inline feedback row under every response (feature #12)
- Audit log viewer, role-gated (feature #9)
- Ranking transparency, tap-to-expand under responses (feature #5) — do not build this before the backend returns structured per-item scores; a fabricated-looking breakdown from prose is worse than no screen

### Tier 3 — depth, once Tier 1–2 are stable
- Role switcher (flip senior_dev → junior_dev and watch a response visibly get filtered — this is still the best demo of role-based filtering)
- Multi-server profiles (switching between separate *RIP* deployments — not RIP+Gateway pairs, since there's only one pair per server now)

Metrics dashboard content (live counts, health snapshot) gets folded into the Activity screen's header rather than earning a dedicated home tab — it's a summary strip above the session list, not a destination of its own.

---

## 7. Open questions to settle before building Tier 1

1. **Session identity.** Sessions currently store `agent_type`, not a human identity. If the Activity screen should say "Priya's session touched this file," that's new plumbing (a lightweight user identity tied to an API key, at minimum). If "other active sessions" (agent-type-only) is good enough for now, say so explicitly in the copy rather than implying a team feature that isn't there yet.
2. **Mount vs. proxy.** Confirm whether merging Gateway's routers directly into RIP's FastAPI app (clean, one process) is feasible in the current codebase layout, or whether a reverse-proxy fallback is needed for this pass. This decision gates every Tier 0 checkbox above.
3. **Naming in code vs. UI.** Internal module names (`gateway/`, `Context Gateway`) can stay as-is for maintainability — only user-facing strings need to drop the "second product" framing. Worth a quick grep of existing Flutter strings/screens for any place "Gateway" already leaked into UI copy from the old plan, so it can be renamed before Tier 1 ships.

---

## 8. Suggested build order (ready to hand to an agent)

```
Tier 0 — Backend (blocking, do first)
  [ ] Mount Gateway REST routers into RIP's FastAPI app / unify via reverse proxy
  [ ] Verify shared Postgres for session/audit/feedback tables post-mount
  [ ] Replace metrics stub with real aggregation
  [ ] Add GET /audit list endpoint
  [ ] Add POST /feedback endpoint
  [ ] Add per-source token_allocation to get_context response
  [ ] Fix validate_change diff→symbol resolution
  [ ] Make RIP's always-on status an explicit sources-response field
  [ ] Decide session-identity approach (agent_type-only vs. human identity)

Tier 1 — Mobile (once Tier 0 unification + auth land)
  [ ] Inline intent badge in chat
  [ ] Inline token budget strip in chat
  [ ] Sources settings screen (single list: RIP + external)
  [ ] Activity screen (sessions + conflict history)
  [ ] Inline conflict banner in chat
  [ ] Unified Settings screen (one connection, one role field)
  [ ] MCP config export screen

Tier 2 — Mobile (once feedback + audit endpoints land)
  [ ] Inline feedback row per response
  [ ] Audit log viewer (role-gated)
  [ ] Ranking transparency breakdown per context item

Tier 3 — Mobile (depth)
  [ ] Role switcher
  [ ] Multi-server profiles (single-pair-per-server model)
```
