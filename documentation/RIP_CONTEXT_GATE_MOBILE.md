
# RIP Chat — Live Pipeline Status & Production-Grade Chat Redesign

**Hand this file to the build agent as-is.** It covers one feature end to end: while RIP/Gateway is
assembling an answer, the chat shows a live, honest, step-by-step account of what's happening
("Gathering files from RIP graph", "Enumerating GitHub PRs", "Deduplicating 12 items"...) instead
of a spinner — and the surrounding chat UI is upgraded to match that quality bar throughout.

This plan assumes the single-connection unification from the prior redesign
(`RIP_GATEWAY_UNIFIED_PLAN.md`) is either already done or being done in parallel — every streaming
endpoint below is mounted on the same host:port the app already talks to. Do not stand up a third
connection to deliver this feature.

---

## 0. Product framing (read first, don't skip)

This is not a "loading animation." It is the single best trust-building surface RIP has. Nobody
else shows an agent *what it actually checked* before answering. The steps are not decorative —
every line on screen must correspond to a real event the backend pipeline actually emitted. If the
backend didn't do it, the UI must not claim it did. This is the same honesty rule the rest of RIP's
planning already follows (no screen fabricates data it doesn't have) — it applies here more than
anywhere, because this feature's entire value is "we show you the truth while it happens."

**Design principles for this feature:**

1. **Verb-first, present-tense, no jargon.** "Deduplicating 12 overlapping items," not
   "Running DeduplicationEngine.process()." The user should understand every line without knowing
   RIP's internals.
2. **Real events only.** Every step comes from an actual pipeline stage emitting an actual event.
   No client-side fake delays, no "simulate progress" timers.
3. **Fast steps still show.** Even a 40ms graph query gets a line. Speed is part of the pitch —
   hiding fast steps hides the proof that parallel execution works.
4. **Failure is visible, not swallowed.** A circuit-broken source shows as skipped, in a muted
   warning tone — never silently omitted, never a hard error that blocks the rest of the answer.
5. **It collapses.** Once the answer starts streaming, the step list compresses into a single
   tappable summary chip. Nobody wants to keep reading "Ranking 47 candidates" once they're
   reading the actual answer.
6. **It's reusable proof, not a one-time animation.** The collapsed chip stays attached to that
   message permanently — a user should be able to scroll back to a two-day-old answer and still
   expand it to see exactly what was queried.

---

## 1. Stage taxonomy and copy

This is the exact vocabulary of steps the backend must emit and the frontend must render. Treat
this table as a contract between backend and frontend — both sides build against it.

| Stage id | Backend pipeline source | Example UI line | Notes |
|---|---|---|---|
| `intent` | Intent Classifier | "Reading your request" → "bug_fix · payments domain · 92% confidence" | Two-part: starts immediately, resolves fast |
| `plan` | Multi-Source Planner | "Planning retrieval — 3 sources, 12,000 token budget" | One line, resolves fast |
| `source_start` | Parallel Executor (per source) | "Querying RIP graph…" / "Searching GitHub PRs…" / "Checking Jira ticket…" / "Checking Slack discussion…" | One line per source, all appear together (parallel), each resolves independently |
| `source_done` | Parallel Executor (per source) | "RIP graph — 34 results in 210ms" | Replaces the `source_start` line for that source in place |
| `source_skipped` | Circuit breaker / disabled source | "GitHub — skipped (paused until 14:32)" | Muted/warning tone, not an error tone |
| `source_failed` | Parallel Executor (per source) | "Jira — timed out, continuing without it" | Muted/warning tone |
| `conflict_check` | Session memory | "Checking for conflicts with active sessions" | Quick, usually resolves silently |
| `conflict_found` | Conflict Detector | "⚠ payment_service.py is being edited in another active session" | Elevated tone — see §5, this can interrupt |
| `rank` | Ranker | "Scoring 47 candidates" | |
| `dedup` | Deduplicator | "Removed 12 duplicate items" | Only shown if count > 0 |
| `compress` | Compressor | "Compressing to fit 12,000 token budget" → "28,400 → 11,800 tokens" | Two-part like intent |
| `permission_filter` | Permission Engine | "Applying developer-role access rules" | Only shown if something was actually filtered; otherwise skip the line entirely — don't show a step that did nothing |
| `done` | Response formatter | *(collapses into summary chip, see §6)* | Terminal event, always emitted |

Backend emits **exactly one event per row transition** (`start` → `done`/`failed`/`skipped`). The
frontend never guesses timing — every visual state change is server-driven.

---

## 2. Event schema (backend contract)

```jsonc
// One event per line of this JSON-lines / SSE stream
{
  "session_id": "b3f2...",
  "stage": "source_start",        // one of the stage ids in §1
  "source": "github",             // present for source_* events only
  "status": "started",            // started | done | failed | skipped
  "detail": "Searching GitHub PRs…",   // pre-rendered copy string, backend owns the copy
  "meta": {                       // optional, stage-specific
    "count": 34,
    "ms": 210,
    "resume_at": "14:32",
    "before_tokens": 28400,
    "after_tokens": 11800,
    "removed": 12
  },
  "seq": 7,                       // monotonically increasing, lets client detect drops/reorder
  "ts": "2026-07-02T10:14:03.221Z"
}
```

Design decision: **the backend owns the copy string** (`detail`), not the frontend. This keeps
wording centralized, translatable later, and guarantees the frontend never has to duplicate the
stage-taxonomy table in Dart. The frontend renders `detail` plus stage-specific iconography/state
color driven by `stage` + `status`.

---

## 3. Transport

- Add one streaming endpoint on the **already-unified** server (same host:port as everything
  else): `GET /chat/stream?session_id=...` or a WS upgrade at `/ws/chat/{session_id}`, whichever
  matches the existing WebSocket pattern already used for indexing progress
  (`WS /ws/index/{job_id}`) — reuse that pattern, don't invent a second transport style.
- Every `get_context` / `search_codebase` / `explain_architecture` / `validate_change` pipeline
  call gets instrumented with an event emitter hook that writes to this stream as the pipeline
  actually executes each stage — this is not a wrapper that fakes events after the fact.
- Stream closes cleanly on `done` or `failed`, same lifecycle discipline as the existing indexing
  WebSocket.
- Reconnect behavior: if the socket drops mid-stream, the client reconnects and requests events
  from the last `seq` it saw; the backend replays missed events from an in-memory ring buffer keyed
  by `session_id` (a few seconds of buffer is enough — this is not meant to survive an app restart
  mid-stream, just a flaky network blip).

---

## 4. Frontend architecture (Flutter)

- New model: `PipelineEvent` (mirrors the schema in §2) and `PipelineTrace` (an ordered, mutable
  list of `PipelineEvent` keyed by `stage`+`source`, so a `source_done` event updates the existing
  `source_start` row in place instead of appending a new one).
- New provider: `pipelineStreamProvider(sessionId)` — opens the stream, folds incoming events into
  a `PipelineTrace`, exposes it to the chat message widget tied to that session.
- Extend the existing `ChatMessage` model (already has `blocks` and `isLoading` per the prior
  Flutter work) with a `PipelineTrace? trace` field. No new message type — this rides on the
  message that's already mid-flight.
- New widget: `PipelineStepList` — renders the live, expanded step list while `isLoading == true`.
- New widget: `PipelineSummaryChip` — the collapsed one-line summary shown once the message
  resolves ("4 sources · 11,800 tokens · 1.2s ▸"), tappable to re-expand `PipelineStepList` inline,
  permanently available on that message (not just during the loading moment).
- `rip_message.dart` (already dispatches block types) gets one more branch: render
  `PipelineStepList` above the response blocks while loading, then swap to `PipelineSummaryChip`
  once `isLoading` flips false — this is a state transition, not a new screen.

**Visual/motion spec** (hand to whoever builds the widget):

- Each step row: leading state icon (pending dot → spinner → check / warning triangle), label text,
  trailing meta (`34 results · 210ms`) in a dimmer/smaller weight than the label.
- Parallel source rows appear together, top-aligned, each animates independently — this is the
  single clearest visual proof that execution is parallel, don't serialize the reveal artificially.
- New row: fade + slight upward slide, ~150ms ease-out. Respect reduced-motion settings (fade only,
  no slide, if the OS accessibility setting requests it).
- Warning-state rows (`skipped`/`failed`) use a muted amber, never red — red is reserved for
  `conflict_found` and hard errors.
- Collapse transition (step list → summary chip): height-collapse + crossfade, ~200ms, triggered the
  moment the first token of the real answer is ready to stream — don't make the user wait for the
  step list to finish animating before they can start reading.

---

## 5. Conflict handling (interrupt, don't queue)

`conflict_found` is the one event that doesn't just add a row — per the earlier unified plan, a
detected conflict should surface as an inline banner in the conversation, not buried in a step list
the user has to expand. Implementation: `PipelineStepList` renders `conflict_found` as a distinct,
non-collapsing banner segment above the rest of the trace, styled apart from the ordinary step rows,
and it stays visible even after the step list itself collapses to the summary chip (the conflict
warning is important enough to survive collapse; the routine steps are not).

---

## 6. Post-response summary chip (ties into the prior unified plan)

The collapsed chip is the same surface the earlier plan called the "inline token strip" and "intent
badge" — don't build three separate affordances. One chip, tap to expand, shows:

- Intent + domain + confidence (from `intent` event)
- Sources queried, with per-source result counts (from `source_done`/`source_skipped` events)
- Token before/after (from `compress` event)
- Total elapsed time (from first `seq` timestamp to `done` timestamp)
- Feedback row (thumbs / missing / irrelevant) anchored below the expanded chip — see Phase 9

---

## 7. Fallback behavior

- If the client can't establish a stream (older network, proxy issue), fall back to a plain
  "Working…" indicator with no step detail — never fall back to fabricated/simulated steps. It is
  better to show nothing than to show steps that didn't really happen.
- If the stream connects but the backend hasn't instrumented a given pipeline call yet (partial
  rollout during Phase 1–2 below), the same rule applies: show "Working…" for that call, not a
  guessed step list.

---

## 8. Non-goals

- No client-side progress simulation/fake timers, ever (see §0).
- No separate "pipeline inspector" screen for this pass — the trace lives on the message that
  produced it. A dedicated searchable history of traces is future scope, not part of this build.
- No streaming step list for pure CLI/MCP agent calls — this is a mobile/chat UI feature only; MCP
  agents get their result directly, they don't need a step list rendered for them.

---

## 9. Build plan — Phase 0 to full

### Phase 0 — Copy, states, and motion spec sign-off
- [ ] Confirm the stage taxonomy in §1 against the actual current pipeline stage names in the
      Gateway codebase (classifier → planner → executor → session/conflict → ranker → dedup →
      compressor → permission filter) and adjust wording only if a stage's real behavior doesn't
      match the example copy.
- [ ] Confirm icon/color states for: pending, in-progress, done, skipped, failed, conflict.
- [ ] Confirm reduced-motion behavior is testable on at least one device.
- [ ] Checkpoint: table in §1 is the frozen contract both sides build against.

### Phase 1 — Backend event emission
- [ ] Add an `EventEmitter`/callback hook threaded through the existing pipeline orchestrator
      (classifier → planner → executor → conflict detector → ranker → dedup → compressor →
      permission filter → formatter), firing one event per stage transition per §2's schema.
- [ ] Instrument the parallel executor specifically so each source's `source_start`/`source_done`/
      `source_failed`/`source_skipped` fires independently and concurrently — do not serialize
      emission just because it's easier to code.
- [ ] Add an in-memory ring buffer per `session_id` for reconnect replay (last N events, a few
      seconds' worth).
- [ ] Unit test: run one full `get_context` call against a mocked source set and assert the exact
      ordered event sequence matches expectations, including skip/failure paths.
- [ ] Checkpoint: pipeline emits a verifiable, ordered event stream for a real call, headless (no
      frontend needed to verify this phase).

### Phase 2 — Streaming transport
- [ ] Add the streaming endpoint (`WS /ws/chat/{session_id}` or SSE equivalent) on the **unified**
      server from the prior plan — verify it lives on the same port as every other route, no new
      connection config needed on the client.
- [ ] Wire the endpoint to replay ring-buffer events on reconnect using `seq`.
- [ ] Wire clean stream closure on `done`/`failed`.
- [ ] Load test: confirm concurrent streams for multiple sessions don't cross-deliver events.
- [ ] Checkpoint: a raw WS/SSE client (e.g. `websocat`/curl) can watch a real call's events end to
      end.

### Phase 3 — Flutter streaming client and state model
- [ ] Add `PipelineEvent` and `PipelineTrace` models.
- [ ] Add `pipelineStreamProvider(sessionId)` with reconnect-with-replay logic.
- [ ] Extend `ChatMessage` with `trace` field; confirm existing Drift persistence layer can store a
      serialized trace alongside the message (so re-opening the app still shows the collapsed chip
      with full detail on tap, not just "message complete").
- [ ] Checkpoint: provider correctly folds a real event stream into an ordered, source-keyed trace
      in a widget test using recorded fixture events from Phase 1's unit test.

### Phase 4 — Step list UI
- [ ] Build `PipelineStepList` per the visual/motion spec in §4.
- [ ] Build `PipelineSummaryChip` (collapsed state) per §6.
- [ ] Build the conflict banner treatment per §5.
- [ ] Build the muted skip/fail row treatment.
- [ ] Checkpoint: both widgets render correctly against Phase 1's fixture event sequences,
      including a skip and a conflict case, without a live server.

### Phase 5 — Chat integration
- [ ] Wire `rip_message.dart` to show `PipelineStepList` while `isLoading`, collapse to
      `PipelineSummaryChip` the moment the answer's first content block is ready.
- [ ] Confirm the collapse timing doesn't block the answer from starting to render — steps finish
      collapsing *around* the answer, not *before* it.
- [ ] Confirm scrollback: reopening an old message still shows a tappable summary chip with full
      expand detail (from persisted trace, not a live stream).
- [ ] Checkpoint: end-to-end manual test against a live unified server — ask a real question, watch
      real parallel source rows resolve independently, confirm collapse and re-expand both work.

### Phase 6 — Fallback and resilience
- [ ] Implement the "Working…" no-detail fallback for stream-unavailable and
      pipeline-not-yet-instrumented cases per §7.
- [ ] Implement reconnect-on-drop using stored `seq`.
- [ ] Checkpoint: kill the network mid-stream on a real device, confirm reconnect recovers the trace
      instead of stalling or duplicating rows.

### Phase 7 — Feedback loop hookup
- [ ] Attach the feedback row (thumbs / missing / irrelevant chips, from the prior plan's Tier 2
      feature) below the expanded summary chip, submitted via the existing `POST /feedback`
      endpoint once that lands.
- [ ] Checkpoint: submitting feedback doesn't require re-expanding the trace every time — the chip
      and feedback row coexist in the collapsed state.

### Phase 8 — Verification and polish gate
- [ ] Confirm every line ever shown in the UI traces back to a real backend event — do a manual
      audit pass reading the widget code specifically looking for any hardcoded/simulated copy.
- [ ] Confirm accessibility: reduced motion respected, step rows readable by screen reader in
      correct order.
- [ ] Confirm performance: no visible jank when 4+ sources resolve within the same 100ms window.
- [ ] Confirm the whole feature works with zero regressions to existing chat behavior when the
      backend hasn't emitted any events yet (very first cold call to a freshly upgraded server).
- [ ] Final checkpoint: this feature is done when a user can ask a real question, watch an honest,
      real-time account of what RIP checked to answer it, and later scroll back and re-open that
      same account on a two-day-old message.# RIP + Context Gateway — Unified Product & Mobile Redesign Plan

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
```# Context Gateway → Mobile App: Feature Audit & Integration Plan

## PART 1 — WHAT THE CONTEXT GATEWAY ACTUALLY IS TODAY

Before deciding what goes into the mobile app, this section separates three categories, evidence-first, based on the actual Phase 0–15 build history and the prior REST/MCP audit:

- **A — Built and already reachable over REST/MCP** (safe to wire into mobile immediately)
- **B — Built internally but NOT exposed over REST yet** (needs a thin router before mobile can touch it)
- **C — Only partially real** (stub, placeholder, or weakly wired — needs backend work before mobile can honestly show it)

Getting this categorization right matters because a mobile screen that displays a stub as if it were live data is worse than not having the screen at all.

---

### 1.1 Intent Classification

**What it does:** Reads a task description, classifies it into one of six intent types (`bug_fix`, `feature_addition`, `refactor`, `architectural_question`, `investigation`, `documentation`), detects a domain (payment, auth, api, database, notification, infrastructure), assigns a risk level, and returns a confidence score. Falls back to an LLM few-shot classifier below a confidence threshold.

**Category: A** — reachable indirectly through `get_context`, which returns `intent`, `confidence`, and `domain` in its response payload.

**Mobile relevance:** High. This is the single most "explainable" piece of the Gateway — showing *why* a response was shaped the way it was (intent + domain + confidence) turns the Gateway from an invisible black box into something a user can audit.

---

### 1.2 Multi-Source Planner and Token Budgeting

**What it does:** Builds an ordered retrieval plan from the classification — which sources to query, in what priority, with what token allocation per source. Enforces a reserve percentage and minimum-per-source budget.

**Category: A** (plan summary is returned as part of `get_context`) / **B** (the full `Plan` object with per-source token allocation is not separately exposed as its own endpoint — it's currently folded into the final response, not queryable on its own after the fact).

**Mobile relevance:** Very high — this is the "token management" the user specifically asked for. A mobile view that shows *where the token budget actually went* (e.g. "7,200 → RIP, 2,400 → GitHub, 2,400 reserve") is the most concrete, demo-able proof that the Gateway is doing something worth paying attention to.

---

### 1.3 Source Abstractions (RIP, GitHub, Jira, Slack)

**What it does:** A registry of sources with health tracking. RIP is always-on. GitHub/Jira/Slack are optional, individually enableable/disableable.

**Category: A for GitHub/Jira/Slack toggle** (`POST /api/sources/{name}/enable|disable` is wired) / **C for RIP** — per the prior audit, RIP cannot be toggled through this endpoint, since it's treated as a mandatory core source rather than an optional one. This is a real, known gap, not an oversight to paper over.

**Mobile relevance:** High. This maps directly onto a "Sources" settings screen — but the RIP row on that screen needs to be visually distinct (always-on, no toggle) rather than mobile pretending it's a switch that works.

---

### 1.4 Parallel Executor, Retry, Circuit Breakers

**What it does:** Executes all planned source queries concurrently, retries transient failures with backoff, and opens a circuit breaker (stops calling a source for 5 minutes) after repeated failures within a rolling window.

**Category: A** — circuit breaker state is part of source health, which is exposed via `GET /api/sources/`.

**Mobile relevance:** Medium-high. A "this source is temporarily paused due to repeated failures, resuming at HH:MM" indicator is a genuinely useful operational signal, especially for a mobile user who isn't watching server logs.

---

### 1.5 Tokenizer, Ranker, Deduplicator, Compressor

**What it does:** Counts tokens precisely, scores every retrieved item on five weighted dimensions (semantic similarity, graph centrality, recency, pattern match, source authority — weights shift per intent type), deduplicates near-identical items across sources, then fills the token budget greedily by score until the budget is exhausted, summarizing overflow items instead of dropping them silently.

**Category: A** (final compressed output + token counts are in the `get_context` response) / **B** (the individual per-item scores — i.e., *why item X ranked above item Y* — are computed internally but not currently returned as structured, inspectable data; the audit only surfaced this as narrative markdown, not as a queryable breakdown).

**Mobile relevance:** This is the deepest "trust" feature available. Most AI tooling asks users to take relevance on faith. Exposing even a simplified version of "why this was included, why that was excluded" would be a genuine differentiator — but it requires a small backend addition first (return the per-item score breakdown as structured data, not just prose).

---

### 1.6 Session Memory and Conflict Detection

**What it does:** Every `get_context` call creates a session row (agent type, task, intent, domain, risk, files accessed, nodes accessed, sources used, token stats, status, timestamps). Before returning a response, the Gateway checks all *other* active sessions for file overlap and injects a conflict warning if found.

**Category: A** — `GET /api/sessions/` and `GET /api/sessions/{id}` are wired and return real `Session` model data.

**Mobile relevance:** This is effectively "team activity" already, without needing a separate team system to be built. If two people (or two agents) share one Gateway server, their sessions are already visible to each other through this endpoint. Mobile just needs a good UI over data that already exists.

---

### 1.7 Permission Filtering and Audit Logging

**What it does:** Filters ranked/compressed context by role (`junior_dev`, `developer`, `senior_dev`, `ci_agent`) before it's returned, and writes an audit log entry for every access decision (now persisted in PostgreSQL per the production-hardening pass, not just in memory).

**Category: A** for the filtering logic itself (it runs on every `get_context` call) / **B** for audit log *retrieval* — audit entries are written to PostgreSQL, but there is currently no confirmed REST endpoint to *list/query* them. That needs a small new router (`GET /api/audit`) before mobile can show an audit trail.

**Mobile relevance:** High for anyone positioning this as a team/enterprise tool. "Who accessed what, filtered how" is exactly the kind of thing a team lead would open the app specifically to check.

---

### 1.8 MCP Server (Tier 1 — Agent-Facing)

**What it does:** Exposes exactly four tools to AI agents — `get_context`, `validate_change`, `search_codebase`, `explain_architecture` — over stdio.

**Category: A** for `get_context` and `search_codebase` (fully wired through the real pipeline) / **C** for `validate_change` — per the earlier audit, this tool passes a diff to what is effectively an impact-by-symbol call, which is a semantic mismatch (impact expects a symbol, not a diff). It "works" in the sense that it returns something, but not in the sense that it's answering the question it claims to answer.

**Mobile relevance:** Mobile doesn't call MCP directly (MCP is for agents, not phones) — but mobile is the natural place to **generate and share MCP config** for connecting Claude Code / Cursor / Codex to a user's Gateway instance. That's a config-export feature, not a live-data feature.

---

### 1.9 HTTP Server, Auth, Rate Limiting

**What it does:** FastAPI app with health/context/validate/sessions/sources/metrics routers, plus rate-limiting middleware.

**Category: A** for health, context, sessions, sources / **C** for metrics — the prior audit explicitly found `GET /api/metrics` returns **placeholder constants**, not real aggregated data. Also flagged: **no API-key/bearer auth currently exists on Gateway REST or Gateway MCP**, even though RIP's own server has full API-key auth. This is a real security gap that matters a lot once a mobile app is pointed at a Gateway over the network.

**Mobile relevance:** Metrics is the natural "dashboard home screen" — but it cannot honestly ship until the backend stub is replaced with real aggregation (active session count, tokens retrieved/delivered, source health, conflict count). Auth is a **blocking prerequisite**, not a nice-to-have, before any Gateway mobile feature goes further than localhost testing.

---

### 1.10 CLI (`gateway start/status/sources/mcp config`)

Not directly mobile-relevant — this is a developer-machine tool. Mobile's equivalent of `gateway mcp config` is "generate and share/QR-export MCP config," covered in 1.8.

---

### 1.11 Learning Loop (Feedback → Scorer Weights)

**What it does:** Accepts `rating`, `was_helpful`, `missing_context`, `irrelevant_context` per session and adjusts ranking weights based on that feedback over time.

**Category: B** — the storage model (`feedback` table) and the weight-adjustment logic exist per the TASK.md checkpoints, but there is no confirmed `POST /api/feedback` (or equivalent) REST endpoint in the audited router list. This needs a new endpoint before mobile can submit feedback at all.

**Mobile relevance:** Very high, and genuinely differentiated — a thumbs up/down plus "this missed something" on every chat response, submitted straight to the learning loop, is the kind of feature that makes the mobile app not just a viewer but an active part of making the Gateway better. Requires the new endpoint first.

---

## PART 1 SUMMARY TABLE

| Feature | Status | Mobile-ready today? |
|---|---|---|
| Intent classification display | A | Yes — comes free with `get_context` |
| Token budget breakdown (per source) | A/B | Partial — total shown, per-source split needs a small response-shape addition |
| Source health + enable/disable | A (except RIP) | Yes, with RIP shown as always-on |
| Circuit breaker status | A | Yes |
| Ranking transparency ("why this was included") | B | No — needs structured score export first |
| Sessions / team activity | A | Yes |
| Conflict detection | A | Yes |
| Role-based permission filtering | A (server-side) | N/A — enforced automatically, nothing to build on mobile except *showing* your current role |
| Audit log viewer | B | No — needs a list endpoint first |
| MCP config export | A (data exists via CLI logic) | Yes, as a config-generation screen |
| Metrics dashboard | **C — stub** | **No — blocked until backend returns real data** |
| Feedback submission | B | No — needs a new endpoint first |
| Gateway authentication | **C — missing entirely** | **Blocking — must exist before any of this ships past localhost** |

---

## PART 2 — WHAT THIS MEANS FOR THE MOBILE APP

Given Part 1, the mobile feature set splits cleanly into three build tiers. Building in this order avoids shipping screens that lie about what's happening on the backend.

### TIER 0 — Backend prerequisites (must happen before *any* Gateway mobile work)
1. Add API-key authentication to Gateway REST and Gateway MCP (currently has none — RIP already has this pattern built, reuse it).
2. Replace the `GET /api/metrics` stub with real aggregation: active session count, total tokens retrieved/delivered, per-source health snapshot, active conflict count.
3. Add `GET /api/audit` (or equivalent) to list persisted audit log entries with filtering by session/role/date.
4. Add `POST /api/feedback` accepting `session_id`, `rating`, `was_helpful`, `missing_context`, `irrelevant_context`.
5. Extend `get_context`'s response shape to include a `token_allocation` breakdown by source (not just the total used), and — if feasible without a large rewrite — a simplified per-item score summary for the top N included items.
6. Fix `validate_change` to actually accept a diff and resolve it to affected symbols before calling impact, instead of passing the diff straight through.
7. Decide RIP's toggle story explicitly: either make it genuinely toggleable, or make the "always on" state a first-class field in the sources response instead of an implicit gap.

None of Tier 1–3 below should be built against a Gateway that's still missing Tier 0 auth — that's not a UX gap, it's a real security hole once this leaves localhost.

---

### TIER 1 — Ship immediately once Tier 0 auth lands (data already real)

**1. Gateway Dashboard (new home tab, separate from RIP chat)**
- Connection status to Gateway server (separate from RIP server — these are two different backends today and the app should be honest about that distinction, not blend them into one status dot)
- Active sessions count, live-updating
- Source health strip: RIP (always on) · GitHub · Jira · Slack, each with a status dot and last-checked time
- "X sources queried, Y ms" summary from the most recent `get_context` call

**2. Sessions & Team Activity screen**
- List of all sessions (own + others sharing the same Gateway), each showing: agent type, task description, intent badge, domain, files touched, status (in_progress/completed/failed), started/ended time
- Tap into a session to see its full detail: files accessed, sources used, tokens retrieved vs. delivered, outcome
- **Conflict banner**: if any of your active sessions overlaps files with someone else's active session, surface it prominently — this is the single most "wow, it actually caught that" feature available, and it's fully real today

**3. Token Budget view (per chat response, inline)**
- Under each RIP Chat response that went through the Gateway, show a collapsible strip: total budget, tokens used, and (once Tier 0 item 5 lands) a bar breakdown by source — "RIP: 7,200 · GitHub: 2,400 · reserve: 2,400"
- This is the most direct, demo-able answer to "token management" — make it visible by default, not buried three taps deep

**4. Sources settings screen**
- RIP: always-on badge, health status, last query latency
- GitHub / Jira / Slack: toggle on/off, connection status, "configure credentials" (opens a form for whatever the source needs — API tokens etc.)
- Circuit breaker state shown per source: "Paused until 14:32 after repeated failures" instead of just "offline"

**5. Intent transparency (inline in chat)**
- Small badge on each Gateway-routed response: intent type, confidence %, detected domain, risk level
- Tap to expand into a one-line explanation of what that meant for retrieval ("bug_fix → recency-weighted, RIP + GitHub queried, Slack skipped")

**6. MCP Config export**
- Screen that generates the same JSON `gateway mcp config` produces on desktop, with a copy button and a QR code (for scanning into a laptop-side setup flow) — genuinely useful since MCP config is exactly the kind of fiddly JSON people currently have to type by hand

---

### TIER 2 — Ship once the two remaining backend endpoints land

**7. Feedback on every response**
- Thumbs up/down under each Gateway response
- "Missing something?" and "Included something irrelevant?" quick-tag chips that feed straight into `missing_context` / `irrelevant_context`
- This is what makes the mobile app an active participant in the learning loop, not just a viewer

**8. Audit Log viewer** (role-gated — likely `senior_dev`/`ci_agent` only, enforced server-side via the same permission engine that already filters context)
- Chronological list of access decisions: who, what role, what was filtered, when
- Filter by session, by date range, by role
- This is the screen a team lead opens specifically to answer "did the junior dev's agent see something it shouldn't have" — worth building well, not as an afterthought

**9. Ranking transparency ("why was this included")**
- Once structured per-item scores are returned, show a simple breakdown per context item: the five weighted scores (semantic/centrality/recency/pattern/authority) as a compact bar or radar, so a curious user can see *why* item X outranked item Y
- This is genuinely rare in any context-management product today — most systems ask for blind trust

---

### TIER 3 — Real "settings" depth (once Tier 1–2 are stable)

**10. Full Settings restructure**
Split settings cleanly into three sections instead of one flat list, since there are now genuinely two backends:
- **RIP Server** — URL, API key, connection test, indexed project management (existing)
- **Gateway Server** — URL, API key, connection test, default role for this device (junior_dev/developer/senior_dev/ci_agent), token budget default, source toggles
- **App** — theme, chat history management, notification preferences (if conflict alerts ever become push notifications), about/version

**11. Role switcher**
- Let the user pick which role their requests are made under (assuming their API key is provisioned for multiple roles, or the app supports multiple saved Gateway identities) — directly demonstrates the permission-filtering feature by letting someone flip from `senior_dev` to `junior_dev` and watch a response visibly get filtered

**12. Multi-Gateway / multi-server profiles**
- If someone works across more than one team's Gateway instance (or a personal + work setup), let them save multiple RIP+Gateway server pairs and switch between them from one tap — this is the natural mobile-specific feature that desktop tooling doesn't need as urgently

---

## PART 3 — WHAT NOT TO BUILD YET

Being explicit about scope boundaries, matching how prior phases in this project have been scoped:

- Do not build a mobile UI for *editing* the Gateway's strategy table (which sources get queried for which intent) — that's a server-config concern, not a mobile one, and exposing it risks someone breaking retrieval quality from their phone by accident.
- Do not build push notifications for conflict detection in this pass — surface conflicts when the app is open, not as a background service, until there's a clear signal this is wanted.
- Do not attempt to build a *new* team/user-account system. Team activity already exists implicitly through shared session visibility on one Gateway server — building a parallel user system would duplicate what RIP's API-key system plus Gateway sessions already provide.
- Do not expose raw audit log PostgreSQL rows unfiltered — the audit viewer must go through the same permission engine as everything else, or it becomes the one screen that leaks what the rest of the system is built to protect.
- Do not build the ranking-transparency screen (Tier 2, #9) before the backend actually returns structured per-item scores — a mobile screen that fabricates a plausible-looking breakdown from prose is worse than not having the screen.

---

## PART 4 — SUGGESTED BUILD ORDER (TASK.md-style, ready to hand to an agent)

```
Tier 0 — Backend (blocking, do first)
  [ ] Add API-key auth to Gateway REST + MCP
  [ ] Replace /api/metrics stub with real aggregation
  [ ] Add GET /api/audit list endpoint
  [ ] Add POST /api/feedback endpoint
  [ ] Add per-source token_allocation to get_context response
  [ ] Fix validate_change diff→symbol resolution
  [ ] Make RIP's always-on status explicit in /api/sources/ response

Tier 1 — Mobile (once Tier 0 auth lands)
  [ ] Gateway Dashboard home tab
  [ ] Sessions & Team Activity screen + conflict banner
  [ ] Inline token budget strip per chat response
  [ ] Sources settings screen (RIP always-on + toggleable others)
  [ ] Intent transparency badge in chat
  [ ] MCP config export + QR code screen

Tier 2 — Mobile (once remaining endpoints land)
  [ ] Inline feedback (thumbs + missing/irrelevant tags)
  [ ] Audit log viewer (role-gated)
  [ ] Ranking transparency breakdown per context item

Tier 3 — Mobile (settings depth)
  [ ] Split Settings into RIP Server / Gateway Server / App
  [ ] Role switcher
  [ ] Multi-Gateway server profiles
```

---

## OPEN QUESTION BEFORE BUILDING

Two things worth deciding before writing any code, since they change the shape of Tier 1:

1. **Is one phone expected to represent one person, or one team's shared view?** If it's shared-team-view, the Sessions screen needs a "whose session is this" identity layer that doesn't fully exist yet (sessions currently store `agent_type`, not a human user identity). If it's one-person, the "team activity" framing should really be called "other active sessions" — accurate, but less marketable.
2. **Does the mobile app talk to one Gateway server per install, or does Tier 3's multi-server profile matter from day one?** This affects whether server switching gets built into the settings architecture now or bolted on later.