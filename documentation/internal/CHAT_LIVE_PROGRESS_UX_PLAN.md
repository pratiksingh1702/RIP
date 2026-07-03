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
      same account on a two-day-old message.
