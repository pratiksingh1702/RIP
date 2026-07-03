# RIP Mobile — Gateway Settings, Dynamic MCP Sources & Settings IA Plan

**Hand this file to the build agent as-is.** It covers making Context Gateway's behavior fully
editable from the phone — including adding arbitrary MCP servers (GitHub, Jira, Slack, Linear,
Notion, or anything else that speaks MCP) — without ever asking the user to configure a second
connection, and without ever turning the chat screen into anything but one screen.

This plan builds directly on the two prior plans and must not contradict them:

- `RIP_GATEWAY_UNIFIED_PLAN.md` — one server connection, one API key, Gateway mounted inside RIP's
  app. Every endpoint below is mounted there. No exceptions.
- `CHAT_LIVE_PROGRESS_UX_PLAN.md` — the live step-by-step pipeline trace in chat. Any new source a
  user adds here must show up in that trace exactly like RIP/GitHub/Jira/Slack already do — same
  event schema, same step rows, no special-casing.

---

## 0. The rule this whole plan follows

**Settings can branch as deep as it needs to. Chat cannot.**

Today's IA already treats these as separate concerns and that's correct — keep going in that
direction. Adding "manage 6 different MCP servers with credentials and test-connection flows" is a
Settings-depth problem, not a chat-surface problem. The chat screen's only job stays: show messages,
show the live trace, show the response. It never grows a "sources" tab, a "servers" tab, or an
"add connector" button of its own. Every one of those lives under Settings, reached the same way
Settings is reached today (drawer → Settings), and the chat screen doesn't change shape no matter
how much settings depth gets added underneath it.

---

## 1. What "editable from mobile" actually means

Today, per the existing build history, `GitHub`/`Jira`/`Slack` are three hardcoded optional
sources with an enable/disable toggle each (`POST /api/sources/{name}/enable|disable`). That's
static — three names baked into the source registry at build time. This plan replaces that with a
**dynamic source registry**: any number of MCP-compatible servers, added and removed at runtime,
from the phone, without a redeploy.

Two tiers of what becomes editable:

1. **Built-in source behavior** (existing three, generalized): enable/disable, credentials,
   priority hints — same as today, just no longer hardcoded to exactly three names.
2. **Arbitrary MCP servers**: user adds a new source by pointing at any MCP server (their own
   internal tool, a community MCP server, Linear, Notion, a second GitHub org, whatever). The
   planner, executor, ranker, and permission engine must treat it exactly like a built-in source
   from the moment it's added — no second-class citizens.

Also editable from mobile, not just source list:
- Token budget defaults (total budget, reserve %, minimum-per-source floor)
- Default role for this device/API key
- Per-source priority/domain hints (so the planner knows *when* to query a custom source)
- Circuit breaker sensitivity is **not** exposed to mobile — that's an operational tuning knob for
  whoever runs the server, not a per-user setting. Keep it server-config-only, matching the earlier
  plan's rule about not exposing strategy-table editing to mobile (see §7, Non-goals).

---

## 2. Core engine changes required (this is the real work)

The mobile UI is the easy part. Nothing above is usable until the Gateway's internals stop assuming
a fixed source list. Concretely:

### 2.1 Source registry becomes data, not config
- Move from a hardcoded `{rip, github, jira, slack}` set to a DB-backed table of registered
  sources: `id, name, kind (builtin|mcp), transport (stdio|http|sse), endpoint_url, auth_type,
  credential_ref, domain_hints[], priority_hint, enabled, health_status, created_by, created_at`.
- `credential_ref` points at an encrypted secret, never a plaintext column — see §2.4.
- RIP itself stays a special always-on row (per the earlier plan's "make RIP's always-on status an
  explicit field" item) — it is not deletable, not disableable, but otherwise lives in the same
  table so every code path that iterates "sources" doesn't need a special case for it.

### 2.2 Base MCP client interface becomes the on-ramp for *any* source
The existing "base source/MCP client interface" (already built per the Gateway's Phase 4 history)
is exactly the right abstraction — it was built anticipating this. The work here is:
- Confirm the interface truly only needs `endpoint`, `transport`, and `auth` to construct a working
  client, with no GitHub/Jira/Slack-specific assumptions leaking in.
- Add a generic `DynamicMCPSource` implementation that satisfies the interface purely from registry
  row data — no code changes required to add a new server, only a new row.
- Existing GitHub/Jira/Slack clients can stay as-is for backward compatibility, or be migrated to
  rows of `kind=builtin` that happen to use richer preset logic (see §3.2) — either is fine as long
  as the executor doesn't need to know the difference.

### 2.3 Planner must reason about sources it's never seen before
Today's strategy table maps intent/domain → a fixed list of known sources. That must become:
- A **base strategy table** for built-in sources (unchanged behavior, don't regress this).
- A **domain-hint matching layer** for dynamic sources: if a user tags a custom source with
  domain hints (`payments`, `infra`, `docs`, etc.) at add-time, the planner includes it whenever
  a task's classified domain matches. If untagged, the source is included at a low default priority
  for all tasks, never higher priority than a domain-matched built-in source — untagged custom
  sources should participate, not dominate.
- This is additive logic layered on the existing planner, not a rewrite of intent classification.

### 2.4 Credential storage
- New sources may need an API token/OAuth secret. Store encrypted at rest (reuse whatever secret
  handling pattern the production-hardening pass already established for Gateway — the build
  history already lists "harden secret management, remove default credentials" as done; extend that
  same mechanism to per-source dynamic credentials instead of introducing a second pattern).
- Mobile never receives the plaintext credential back after creation — same one-time-reveal pattern
  RIP already uses for its own API keys (`repo api-keys create` shows the key once). Editing a
  credential means replacing it, not revealing and re-saving it.

### 2.5 Executor, ranker, permission engine, audit — no special casing
- Circuit breaker, retry/backoff, and health tracking already operate per-source generically — a
  dynamic source gets this automatically once it's a row in the same table the executor already
  iterates. No new code needed here beyond removing any place that currently hardcodes
  `["rip", "github", "jira", "slack"]` as a literal list instead of reading the registry.
- Permission engine's role-based filtering and audit logging must log dynamic sources with the same
  fidelity as built-in ones — an auditor asking "what did this agent access" must see custom MCP
  servers in that trail exactly like GitHub/Jira/Slack today.
- Live pipeline trace (`CHAT_LIVE_PROGRESS_UX_PLAN.md`, §1) needs zero changes — `source_start` /
  `source_done` events are already keyed by source name/id generically, so a newly added MCP server
  shows up in the live trace the first time it's queried, automatically.

---

## 3. New/changed backend endpoints (all mounted on the existing unified server)

```
GET    /gateway/sources                 # list all sources: built-in + dynamic, with health
POST   /gateway/sources                 # register a new MCP source
GET    /gateway/sources/{id}            # detail
PATCH  /gateway/sources/{id}            # edit name, domain hints, priority, enabled state
DELETE /gateway/sources/{id}            # remove (built-in RIP row is protected, 400s on delete)
POST   /gateway/sources/{id}/test       # test-connection: attempt a lightweight MCP handshake
POST   /gateway/sources/{id}/credential # replace credential (write-only, never returns secret)
GET    /gateway/settings                # token budget defaults, reserve %, default role
PATCH  /gateway/settings                # edit the above
```

### 3.1 Test-connection contract
`POST /gateway/sources/{id}/test` must return within a bounded timeout (a few seconds) with one of:
`ok` (handshake succeeded, tool list retrieved), `auth_failed`, `unreachable`, `timeout`. The mobile
UI's "Test Connection" button maps directly to these four states — no ambiguous "something went
wrong" state; always tell the user which of the four it was.

### 3.2 Preset catalog (convenience, not a hard requirement)
Ship a small preset list (GitHub, Jira, Slack, Linear, Notion) that pre-fills transport/endpoint
pattern and asks only for the credential — this is a UI convenience layered on top of the fully
generic `POST /gateway/sources`, not a different code path. "Add Custom Server" in the same flow
skips the preset and asks for everything (name, endpoint, transport, auth type, credential).

---

## 4. Mobile Settings IA (this is where it's allowed to branch)

Reached the same way as always: drawer → **Settings**. Everything below is new depth under that one
entry point — the drawer itself doesn't grow new top-level items for this feature.

```
Settings
├── Connection                     (existing: one Server URL, one API key, Test Connection)
├── Role & Defaults                (existing: default role dropdown — now also token budget
│                                    defaults live here: total budget, reserve %, min-per-source)
├── Sources                        (NEW — replaces the old static GitHub/Jira/Slack toggle list)
│   ├── RIP                        (always-on row, badge only, no toggle, tap for health detail)
│   ├── [each configured source]   (name, health dot, tap → Source Detail)
│   ├── + Add Source               → Add Source flow (§5)
│   └── (empty state: "No external sources yet. RIP works fully on its own — add a
│        source to let it check GitHub, Jira, Slack, or any MCP server too.")
├── Source Detail (per source)     (NEW — name, endpoint, domain hints, priority, enabled toggle,
│                                    health/circuit-breaker status, Test Connection, Replace
│                                    Credential, Remove Source)
├── Audit Log                      (existing, role-gated — now also shows dynamic-source accesses)
└── App                            (existing: theme, chat history, about)
```

Design rule for this tree: **every leaf is reachable in ≤3 taps from the drawer**, and the back
button always returns to exactly where the user came from (standard platform back stack — no
custom navigation surprises). This is a settings area, not a wizard; users should be able to jump
straight to "Source Detail" for one server without walking through the whole list every time
(deep-linkable from a push/notification later, even though notifications are out of scope now).

---

## 5. Add Source flow

Single bottom-sheet/screen flow, reached only from **Settings → Sources → + Add Source**:

1. **Choose a starting point**: preset tiles (GitHub, Jira, Slack, Linear, Notion — icon + name) or
   a plain "Custom MCP Server" tile at the end of the row.
2. **Preset path**: form pre-fills transport/endpoint pattern; user only supplies the
   credential (token/OAuth) and an optional display name if they want more than one of the same
   preset (e.g. two GitHub orgs).
3. **Custom path**: user supplies name, endpoint URL, transport (stdio/http/sse — http/sse only
   realistically apply on mobile-initiated setup, stdio sources are more of a desktop/local
   concept and can be marked "requires desktop setup" if selected), auth type, credential.
4. **Optional domain hints**: multi-select chips (payments, auth, infra, docs, notifications,
   database, api — same domain vocabulary the intent classifier already uses) so the planner knows
   when this source is relevant. Optional — skipping is fine, see §2.3 fallback behavior.
5. **Test Connection** (required before saving) — uses the four-state contract from §3.1, blocks
   save on `auth_failed`/`unreachable`/`timeout` with a clear inline reason and a retry button;
   allows save immediately on `ok`.
6. On save, the new source appears in the Sources list instantly, with live health, and is
   available to the planner on the very next chat message — no app restart, no re-login, no second
   connection step of any kind.

---

## 6. Visual design direction

Extend the existing design system (`SectionCard`, `StatusBadge`, dark theme tokens already built
per the Flutter production-wiring history) rather than introducing a second visual language for
settings:

- **Source rows** reuse `SectionCard` + `StatusBadge` exactly as the existing Sources concept
  already renders RIP/GitHub/Jira/Slack today — a new dynamic source is visually indistinguishable
  from a built-in one except for its icon (preset icon or a generic plug icon for custom servers).
- **Credential fields** always render masked (`••••••••1234`, last 4 visible) with a single
  "Replace" action — never an editable plaintext field, never a full reveal.
- **Test Connection button** has four explicit visual states matching §3.1 — a spinner state, a
  green check + "Connected" state, an amber "Needs attention" state with the specific reason
  (`auth_failed`/`unreachable`/`timeout`) inline beneath the button, never just a generic error.
- **Domain hint chips** reuse whatever chip component the intent-transparency badge already uses in
  chat (same visual language for "domain" wherever it appears in the app — chat badge and settings
  chips should look like the same concept, because they are).
- **Empty states** get real copy, not a bare icon — see the Sources empty state text in §4 as the
  model for tone: explain what the screen is for in one sentence, then give the one clear action.
- **Destructive actions** (Remove Source) require a confirm step with the source name spelled out in
  the confirmation ("Remove GitHub (acme-corp)? RIP will stop checking it in every answer."), never
  a bare "Are you sure?".

---

## 7. Non-goals

- No mobile UI for editing the *planner's* base strategy table for built-in intents/domains — that
  remains a server-config concern per the original Gateway audit's scope boundary. Mobile can tag
  domain hints on *sources it adds*, but cannot rewrite which sources RIP itself considers core.
- No mobile-side circuit breaker sensitivity tuning (retry counts, cooldown windows) — operational,
  server-side only.
- No OAuth-flow UI polish beyond a functional token/URL entry for this pass — a full in-app OAuth
  browser handoff for presets like GitHub is a fast-follow, not required to ship dynamic sources.
- No multi-tenant source sharing model (i.e., "share my added source with my team") in this pass —
  a source added by one API key is visible to everyone hitting the same server today (same as
  existing sessions/team-activity visibility), and that stays true; no per-user private source list
  is being introduced here.

---

## 8. Build plan — Phase 0 to full

### Phase 0 — Confirm the abstraction actually holds
- [ ] Read the existing base source/MCP client interface and source registry code; confirm it can
      genuinely be constructed from `{endpoint, transport, auth}` alone with zero
      GitHub/Jira/Slack-specific branches. Fix any leaks before building on top of it.
- [ ] Confirm every place that currently hardcodes the source name list (`["rip","github","jira",
      "slack"]`) as a literal, across planner, executor, permission engine, and audit logging.
      List them explicitly so Phase 2 has a checklist to clear.
- [ ] Checkpoint: a written list of every hardcoded-source-list location exists before any code
      changes start.

### Phase 1 — Dynamic source registry (data + migration)
- [ ] Add the `sources` table per §2.1's schema (or extend the existing `source health` model if
      one already exists, rather than duplicating it).
- [ ] Add encrypted credential storage reusing the existing production-hardening secret pattern.
- [ ] Migrate existing GitHub/Jira/Slack config into rows of this table (`kind=builtin`) so nothing
      regresses — their current enable/disable behavior must survive the migration unchanged.
- [ ] Checkpoint: RIP still boots with GitHub/Jira/Slack behaving exactly as before, now reading
      from the new table instead of hardcoded config.

### Phase 2 — Core engine generalization
- [ ] Replace every hardcoded source-list location found in Phase 0 with a read from the registry.
- [ ] Implement `DynamicMCPSource` against the base MCP client interface.
- [ ] Extend the planner with the domain-hint matching layer from §2.3, additive to the existing
      base strategy table — confirm built-in intent/domain behavior is byte-for-byte unchanged for
      tasks that don't touch any dynamic source.
- [ ] Confirm executor circuit breaker/retry, ranker scoring, permission filtering, and audit
      logging all operate on a dynamic source with zero special-casing — write one integration test
      that registers a fake MCP source at runtime and confirms it flows through get_context exactly
      like a built-in source, including appearing correctly in a get_context response and in the
      live pipeline event stream from the prior plan.
- [ ] Checkpoint: a source added purely via API (no code deploy) is queried, ranked, filtered, and
      audited identically to a built-in source.

### Phase 3 — Source management endpoints
- [ ] Implement all endpoints in §3, including the four-state test-connection contract.
- [ ] Implement the preset catalog as a thin convenience layer, not a separate code path.
- [ ] Implement `/gateway/settings` for token budget defaults and default role.
- [ ] Checkpoint: every endpoint in §3 verified against a real registered MCP server end to end,
      including a deliberately wrong credential to confirm `auth_failed` is returned correctly.

### Phase 4 — Mobile Settings IA restructure
- [ ] Rebuild the Sources screen per §4 to read from `GET /gateway/sources` instead of a hardcoded
      three-item list.
- [ ] Build the Source Detail screen (health, domain hints, priority, Test Connection, Replace
      Credential, Remove).
- [ ] Move token budget defaults and default role into Role & Defaults per §4's tree.
- [ ] Checkpoint: Settings → Sources shows RIP as always-on plus every currently registered source,
      live, with correct health/circuit-breaker state per row.

### Phase 5 — Add Source flow
- [ ] Build the preset-tile + custom-tile entry screen per §5 step 1.
- [ ] Build the preset-prefilled form and the full custom form.
- [ ] Build the domain-hint chip picker reusing the existing domain-badge component from chat.
- [ ] Wire the mandatory Test Connection gate before save, with all four states surfaced correctly.
- [ ] Checkpoint: add a real custom MCP server from the phone with zero code changes on the backend,
      see it appear in Sources instantly, then ask a chat question in its domain and confirm it
      shows up in the live pipeline trace on the very next message.

### Phase 6 — Credential lifecycle and destructive actions
- [ ] Implement masked credential display and the Replace flow (write-only, no reveal).
- [ ] Implement the confirm-with-name-spelled-out pattern for Remove Source.
- [ ] Confirm RIP's own row correctly refuses deletion with a clear message, not a generic 400.
- [ ] Checkpoint: no code path anywhere in the mobile app can display a previously-saved plaintext
      credential.

### Phase 7 — Audit and permission fidelity
- [ ] Confirm the Audit Log screen shows accesses to dynamic sources with the same detail as
      built-in ones (who, what role, what was filtered, when).
- [ ] Confirm role-based permission filtering applies to dynamic sources by default (a junior_dev
      role doesn't automatically get more access just because a source is new).
- [ ] Checkpoint: register a source, query it under two different roles, confirm the audit trail and
      filtering behavior differ correctly and are both logged.

### Phase 8 — Visual polish and design QA
- [ ] Confirm every new screen reuses existing design tokens (`SectionCard`, `StatusBadge`, chip
      component, dark theme) with no ad-hoc one-off styling introduced.
- [ ] Confirm empty states, destructive-action confirms, and four-state Test Connection feedback
      all match the copy/tone direction in §6.
- [ ] Confirm the chat screen itself has not changed shape, gained new tabs, or grown any
      source-management UI of its own — settings depth stays entirely under Settings.
- [ ] Checkpoint: a design pass confirms Settings now branches several screens deep cleanly, while
      Chat remains exactly one screen, unchanged in structure from before this plan.

### Phase 9 — Final verification gate
- [ ] End-to-end: fresh install → Setup (one connection) → add two custom MCP sources with
      different domain hints → ask two chat questions, one per domain → confirm each question's
      live trace and final response correctly reflects only the relevant source being prioritized.
- [ ] Confirm removing a source mid-session doesn't break an in-flight pipeline trace referencing
      it (already-emitted events for that source stay visible; the source simply isn't queried
      again after removal).
- [ ] Confirm no regression to RIP/GitHub/Jira/Slack's existing behavior from before this plan.
- [ ] Final checkpoint: a user can, entirely from their phone, register any MCP-compatible server,
      tell RIP when it matters, watch it get used live in the pipeline trace, audit exactly what it
      accessed, and remove it — all without ever configuring a second connection or leaving the
      single chat screen's surrounding one-tap Settings entry point.
