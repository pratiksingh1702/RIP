# RIP — Mobile-Native Per-User Integrations & Project Allocation: Full Plan

**Hand this file to the build agent as-is.** This is Plan 5. It supersedes and merges two earlier
pieces of work into one clean, buildable spec:

- The **per-user credential vault plan** (identity-keyed tokens, OAuth device/auth-code flows,
  source client refactor) — its architecture is correct and is adopted here almost entirely.
- `GATEWAY_OAUTH_BRIDGE_PLAN.md` (Plan 4) — its security requirements (PKCE, state/CSRF, encrypted
  storage, audit logging) carry over, but its assumption of **one shared token per source for the
  whole Gateway** is now wrong and is replaced by the vault plan's per-identity model. Its
  assumption of a custom-URL-scheme redirect for every provider is also replaced — see §3.

This plan also adds one thing neither prior document had: **project allocation.** Connecting a
source is a one-time action; using it is scoped per project. A user connects GitHub once and then
decides which of their indexed repositories it applies to.

It keeps faith with the two structural rules already established across every prior plan:

1. **One server connection, ever** (`RIP_GATEWAY_UNIFIED_PLAN.md`) — nothing here asks for a second
   host, port, or key.
2. **Settings can branch as deep as it needs to. Chat cannot.** (`GATEWAY_SETTINGS_MCP_MOBILE_PLAN.md`)
   — every screen in this plan lives under Settings → Integrations, reached exactly the way Settings
   is reached today.

And it fully answers the requirement driving this plan: **the phone is the complete, sufficient
path.** No Gateway CLI step is required to connect a source. A CLI equivalent exists for headless
server operators who don't have the app, but it is optional parity, not a dependency.

---

## 0. The core UX concept, stated once, simply

Settings → Integrations shows a list of every connectable source. Each tile is in one of three
states: **Not connected**, **Connected**, or **Needs attention**. Tapping a not-connected tile does
whatever is required to connect it — nothing more is asked of the user than "tap, authorize on the
provider's own page, done." Tapping a connected tile opens its detail screen, where the user picks
which of their projects it applies to. That's the entire concept. Every phase below exists to make
that one paragraph true and secure.

---

## 1. Phase 0 — The identity decision (blocking, unchanged from the vault plan)

Adopted: **Option A — the API key is the identity.** One phone, one person, one API key, per the
same assumption the mobile plan has made from the start. Every credential is keyed to
`owner_key_id`, the id of the calling API key.

- [ ] Confirm this is recorded as the decision (it is — no Option B work happens in this plan)
- [ ] Note for the future, not for now: the moment a single API key needs to represent more than one
      human (a shared team key), that's a distinct migration to a person-level identity underneath
      API keys — out of scope here, and every table below is deliberately shaped so that migration
      only ever means re-keying a foreign column, not rebuilding the vault.

---

## 2. Data model — merged and reconciled

The vault plan's schema used a fixed `source_name VARCHAR` enum (`'github'`, `'jira'`, `'slack'`).
That's replaced here with a foreign key into the **dynamic source registry** already built in
`GATEWAY_SETTINGS_MCP_MOBILE_PLAN.md`, so a user's own custom MCP server gets exactly the same
per-user credential handling as GitHub/Jira/Slack — no second class of source.

```sql
-- Already exists from Plan 3 — extended here, not replaced.
-- sources.credential_scope distinguishes who owns the actual token:
--   'shared'   -> one gateway-wide credential, set up by whoever administers the server
--                 (this is the "only the server can handle it" case — a true org-wide
--                 service account, not something any one user's phone should hold)
--   'personal' -> every user connects their own account; token lives in source_credentials
--                 below, keyed per user
ALTER TABLE sources ADD COLUMN credential_scope VARCHAR(10) DEFAULT 'personal';
ALTER TABLE sources ADD COLUMN oauth_flow VARCHAR(20);  -- 'device' | 'auth_code' | 'api_key' | null

-- Per-user token storage. One row per (person, source) pair.
CREATE TABLE source_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    encrypted_token TEXT NOT NULL,
    encrypted_refresh_token TEXT,
    scopes TEXT[] DEFAULT '{}',
    account_label TEXT,                      -- "jane@company.com", "acme-corp org"
    expires_at TIMESTAMPTZ,                  -- null = does not expire
    last_refreshed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',     -- active | expired | revoked | error
    connected_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(owner_key_id, source_id)
);

-- CSRF/replay protection for the auth-code providers (Jira/Slack-shaped flows).
CREATE TABLE oauth_states (
    state VARCHAR(64) PRIMARY KEY,
    owner_key_id UUID NOT NULL,
    source_id UUID NOT NULL REFERENCES sources(id),
    code_verifier VARCHAR(128),              -- PKCE, where supported
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL          -- 10 minutes
);

-- NEW: project allocation. A connected credential is opt-in per project, not global by default.
CREATE TABLE source_project_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_credential_id UUID NOT NULL REFERENCES source_credentials(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_credential_id, project_id)
);

CREATE INDEX idx_source_credentials_owner ON source_credentials(owner_key_id);
CREATE INDEX idx_oauth_states_expiry ON oauth_states(expires_at);
CREATE INDEX idx_source_project_links_project ON source_project_links(project_id);
```

**Default allocation rule:** a freshly connected source is linked to **zero** projects until the
user explicitly allocates it. This is a deliberate default — connecting GitHub should never
silently make it active everywhere; the user chooses where. RIP's own graph/search source is exempt
from all of this (it's inherently project-scoped already, per project index, and not a
per-user-credentialed integration).

---

## 3. Provider flow matrix — decide per provider, don't force one shape

This is the single most important correction from the earlier OAuth bridge plan. Not every provider
needs (or can use) a mobile-captured redirect. Pick the right shape per provider:

| Flow | Providers (initial) | Redirect needed? | Mobile's job |
|---|---|---|---|
| **Device flow** | GitHub | None | Show a short code + a link; user can approve from *any* browser, any device, not necessarily the phone; app polls a status endpoint until approved |
| **Authorization code, Gateway-hosted callback** | Jira, Slack, Asana, Linear, Notion, Google Drive, Salesforce | Yes — a stable HTTPS URL the *Gateway itself* hosts and returns a plain "Connected — you can close this" page from | User taps Connect → app opens the provider's consent page in an in-app browser tab → approves → provider redirects to the **Gateway's** callback, not the app's → app polls a status endpoint until it flips to connected |
| **Shared/admin credential** | Any provider an operator wants to expose org-wide instead of per-user (`credential_scope = 'shared'`) | N/A — set up once by the server operator, not per user | Nothing — the source just appears already connected for everyone, no per-user action available beyond seeing it's active |

**Why Gateway-hosted callback instead of a mobile custom-URL-scheme, as the default for the
authorization-code group:** many OAuth apps (Atlassian, Slack, Google) either don't allow
custom-scheme redirect URIs at all or make registering one needlessly fragile across Android/iOS
versions. A stable HTTPS callback the Gateway already exposes (it's already a public-reachable
server per the unified-connection plan) is simpler, provider-accepted everywhere, and requires zero
platform-specific deep-link plumbing. The tradeoff — the app has to *poll* for completion instead of
being handed the result instantly via deep link — is a fine, honest tradeoff: show a clear "waiting
for you to finish in the browser" state (§6.3) rather than pretending it's instant.

Device flow (GitHub) needs none of this — it's the simplest and most mobile-friendly shape available
and should be preferred whenever a provider supports it.

---

## 4. Backend endpoints

All mounted on the one unified server, no exceptions.

```
GET    /integrations                                # list this user's view of every connectable
                                                      # source: name, credential_scope, oauth_flow,
                                                      # status (not_connected|connected|needs_attention),
                                                      # account_label, scopes, connected_at
POST   /integrations/{source_id}/connect             # starts the right flow for that source's
                                                      # oauth_flow type:
                                                      #  - device: returns { user_code, verification_uri,
                                                      #    device_code, expires_in }
                                                      #  - auth_code: returns { authorize_url, state }
GET    /integrations/{source_id}/status              # poll target for both flow types; also accepts
                                                      # ?device_code=... for the device-flow case so
                                                      # the Gateway can poll the provider on the
                                                      # caller's behalf and report back
GET    /integrations/{source_id}/callback            # Gateway-hosted; only used by the auth_code
                                                      # group; validates state, exchanges code,
                                                      # stores credential, renders a plain success page
DELETE /integrations/{source_id}                     # revoke_credential(); calls provider revoke
                                                      # endpoint if one exists
GET    /integrations/{source_id}/projects            # list this credential's current project links
PUT    /integrations/{source_id}/projects            # body: { project_ids: [...] } — full replace,
                                                      # simplest correct semantics for a checklist UI
```

### 4.1 Device flow sequence (GitHub-shaped)
```
1. Mobile → POST /integrations/{github_id}/connect
2. Gateway → calls GitHub's device code endpoint → returns
     { user_code: "WDJB-MJHT", verification_uri: "https://github.com/login/device", device_code: "...", expires_in: 900 }
3. Mobile → shows the code big and legible, a "Copy code" button, and an "Open github.com/login/device" button
4. User → approves in any browser, any device — this is the one flow that genuinely doesn't need to happen on the phone at all
5. Mobile → polls GET /integrations/{github_id}/status?device_code=...
6. Gateway → polls GitHub's token endpoint server-side each time it's asked; once GitHub reports
   approval, exchanges for a token, stores via vault, returns { status: "connected", account_label }
7. Mobile → shows Connected, moves straight into the Project Allocation step (§6.4)
```

### 4.2 Authorization-code sequence (Jira/Slack-shaped)
```
1. Mobile → POST /integrations/{jira_id}/connect
2. Gateway → generates state + PKCE verifier (stored in oauth_states) → returns
     { authorize_url: "https://auth.atlassian.com/authorize?...&state=...", state: "..." }
3. Mobile → opens authorize_url in an in-app browser tab
4. User → logs in / approves on the provider's own real page
5. Provider → redirects to the Gateway's own hosted callback:
     GET /integrations/{jira_id}/callback?code=...&state=...
6. Gateway → validates state (exists, unexpired, unused) → exchanges code for tokens →
     stores via vault → renders "Connected — you can return to the RIP app" static page
7. Mobile → meanwhile has been polling GET /integrations/{jira_id}/status → sees status flip to
     connected → brings the user back into the app view automatically, moves into Project
     Allocation (§6.4)
```

---

## 5. Source client refactor (unchanged principle from the vault plan, now generalized)

Every source client — built-in (GitHub/Jira/Slack) and dynamic (anything added via Plan 3) — stops
holding a single token at construction time and instead resolves a token per call:

```python
class SourceClient:
    async def query(self, *, owner_key_id: UUID, project_id: UUID, session, **params):
        # 1. Confirm this source is actually linked to project_id for this owner (source_project_links)
        #    — if not linked, raise SourceNotAllocatedError, which the planner turns into a clean
        #    "GitHub isn't connected for this project" skip, not a hard failure.
        # 2. Resolve credential:
        #    - credential_scope == 'shared'  -> fetch the one gateway-wide credential
        #    - credential_scope == 'personal' -> vault.get_credential(session, owner_key_id, source_id)
        # 3. Use the resolved token for this call only. Never cache on self. Never reuse across callers.
        ...
```

- [ ] Refactor GitHub/Jira/Slack clients to this shape
- [ ] Extend `DynamicMCPSource` (Plan 3) to the same shape so custom user-added servers get
      per-user credentials automatically, with zero extra code per new server
- [ ] Add `SourceNotAllocatedError` (new — distinct from `SourceNotConnectedError`) for the
      "connected, but not linked to *this* project" case, so the planner can report the two
      situations differently ("not connected" vs. "connected but not turned on for this repo")
- [ ] Thread `owner_key_id` and `project_id` through the planner/executor call chain — both must be
      available from the authenticated request context (this depends on Gateway REST/MCP auth
      already being live, per the earlier unified plan's Tier 0 — do not start this phase before
      that's confirmed in place)

---

## 6. Mobile UX — complete, end to end

### 6.1 Entry point
Drawer → **Settings → Integrations**. Same reachability rule as every prior plan: this is Settings
depth, not a new top-level surface, not anything visible from the chat screen itself.

### 6.2 Integrations list
A single scrollable list, one row per source (built-in presets + any custom MCP servers the user or
an admin has registered per Plan 3), each row showing: icon, name, and a status pill —
**Not connected** (neutral), **Connected** (green, with `account_label` as a subtitle), **Needs
attention** (amber — expired/error status). Shared-scope sources show a small "Managed by your
organization" subtitle instead of a connect action, since there's nothing for this user to do.

### 6.3 Tapping a not-connected personal-scope row
- If `oauth_flow == device`: show the device-code sheet from §4.1 step 3 — big legible code, copy
  button, open-link button, and a quiet "Waiting for you to approve…" status line that updates the
  moment polling detects success. No timeout scare language until actually near the provider's
  `expires_in` — then a calm "This code expired. Try again."
- If `oauth_flow == auth_code`: show a brief explainer sheet ("You'll be taken to {Provider} to
  approve access, then brought back here.") with a **Continue** button that opens the in-app browser
  tab. While the browser tab is open, the app shows a persistent "Waiting for you to finish in
  {Provider}…" state with a manual "I've approved it — check now" button as a fallback for anyone
  whose browser tab doesn't return focus to the app promptly, alongside automatic polling in the
  background so most people never need that button at all.

### 6.4 Immediately after a successful connect — Project Allocation
This is new relative to both prior documents and is not optional UX — it is the direct answer to
"user can allocate the source to any number of projects." The moment a connect flow succeeds, the
app moves straight into:

- A checklist of the user's indexed projects (same list `GET /projects` already provides), each
  with a checkbox, none pre-checked.
- A one-line explainer above the list: "Choose which of your projects can use {Provider}. You can
  change this anytime from Integrations."
- A **Done** button that calls `PUT /integrations/{source_id}/projects` with the checked set —
  works correctly even if the user checks nothing and taps Done (a connected-but-unallocated source
  is a valid, if inert, state — it simply won't be queried by any project yet).
- This same checklist is reachable later from the Integration Detail screen (§6.5) — it is not a
  one-time-only step; it's a persistent, editable setting.

### 6.5 Tapping a connected row — Integration Detail
- Connected-as label + provider icon
- Status pill (Connected / Needs attention) with the specific reason inline if `needs attention`
  ("Access expired — reconnect to keep using this")
- **Projects using this integration** — the same checklist from §6.4, always editable
- **Reconnect** button (re-runs the connect flow, replacing the stored credential — used both for
  `needs_attention` recovery and for switching which account is connected, e.g. a different GitHub
  org)
- **Disconnect** button — destructive-confirm pattern consistent with every prior plan
  ("Disconnect GitHub (jane@company.com)? RIP will stop checking it in every project it's currently
  used in."), calls `DELETE /integrations/{source_id}`, which cascades the project links away too

### 6.6 Where allocation is visible from the project side (read-only, not a duplicate control)
A project's own detail/status view (wherever `repo status`-equivalent info already surfaces on
mobile) gets one additional line: "Connected integrations: GitHub, Jira" (or "None" if unallocated),
tappable straight into Integration Detail for the relevant one. This is a read-only jump-off point,
not a second place to edit allocation — one source of truth for the actual toggle, per the same
discipline as every other settings surface in this product.

### 6.7 Live pipeline trace integration
No changes needed to the trace mechanism itself. A source skipped for `SourceNotAllocatedError`
renders as a `source_skipped` event with `detail: "GitHub — not enabled for this project"` — visibly
different wording from a circuit-broken or needs-reauth skip, so the user immediately understands
*why* and where to fix it (a direct link from that trace line into Integration Detail's project
checklist is a good fast-follow, not required for the first version).

---

## 7. Security requirements (carried over, applied to the merged model)

1. PKCE for every auth-code provider that supports it (device flow doesn't need it — there's no
   redirect to intercept).
2. `oauth_states` rows are single-use and TTL-expired (10 minutes); a replayed or expired state is
   rejected outright.
3. Tokens encrypted at rest (Fernet + a KEK held outside the database, per the vault plan) — reuse
   the same mechanism Plan 3's dynamic-credential storage already established; one encryption
   pattern for the whole system.
4. Gateway refuses to start in production mode without its vault encryption key set.
5. `GET /integrations` and its detail variants never return a token — `account_label`, `scopes`,
   `status`, `expires_at` only, always.
6. `/connect` and `/callback` endpoints are rate-limited explicitly — this is the most abuse-prone
   surface in the whole plan.
7. Every connect, disconnect, reconnect, and allocation-change event writes to the same audit trail
   Plan 3 already extended for dynamic sources — "who connected what, when, and to which projects"
   is one continuous story, not three separate logs.

---

## 8. Non-goals

- No person-level identity system underneath API keys in this pass (Phase 0's Option B stays
  deliberately deferred).
- No mobile UI for registering a brand-new OAuth app with a provider — that's still a one-time
  server-operator action (env config), unchanged from the earlier OAuth bridge plan.
- No automatic re-allocation — if a new project is created after a source is connected, it starts
  unallocated for that source too, same as day one; the user opts it in explicitly, every time,
  by design.
- No push notifications for "finish your pending authorization" — in-app polling and the amber
  status pill are enough, consistent with the standing decision in every earlier plan.
- No write-scope integrations in this pass (read-only/read-mostly scopes only), unchanged from the
  earlier OAuth bridge plan's scope discipline.

---

## 9. Build plan — Phase 0 to full

### Phase 0 — Identity decision
- [ ] Confirm Option A (API key = identity) as recorded above; no further action needed this pass.

### Phase 1 — Vault and schema
- [ ] Add `source_credentials`, `oauth_states`, `source_project_links` tables + migrations per §2.
- [ ] Extend `sources` with `credential_scope` and `oauth_flow` columns.
- [ ] Add Fernet-based vault crypto module + required, secret, non-default `GATEWAY_VAULT_KEY` env
      var, with a startup check that refuses to boot without it in production mode.
- [ ] Implement `store_credential` / `get_credential` / `revoke_credential` / `list_credentials`
      vault service functions, generalized to `(owner_key_id, source_id)` rather than a fixed
      source-name enum.
- [ ] Unit tests: store→get round-trip decrypts correctly; list never leaks a token; revoke removes
      the row and cascades project links.
- [ ] Checkpoint: vault operates correctly against a fake source_id with no live provider involved.

### Phase 2 — Provider flows
- [ ] Implement GitHub device flow end to end (`connect` returns user_code/verification_uri,
      `status` polls GitHub server-side using `device_code`).
- [ ] Implement the shared authorization-code flow shape (`connect` returns authorize_url/state,
      Gateway-hosted `callback` validates state and exchanges code) and apply it to Jira, then Slack,
      confirming each provider's specific scope/token-type requirements (bot vs. user token for
      Slack, PKCE support for Atlassian) before assuming defaults.
- [ ] Implement the "shared" credential_scope path for any source an operator wants gateway-wide
      instead of per-user (config-seeded, no per-user UI).
- [ ] Checkpoint: complete one real device-flow connection and one real auth-code connection
      manually end to end (curl/Postman acceptable for the callback step) before touching mobile.

### Phase 3 — Source client refactor and planner integration
- [ ] Refactor GitHub/Jira/Slack clients to per-call credential resolution per §5.
- [ ] Extend `DynamicMCPSource` (Plan 3) to the same per-call resolution shape.
- [ ] Add `SourceNotAllocatedError` distinct from `SourceNotConnectedError`; wire both into the
      planner as clean skips, never hard failures.
- [ ] Thread `owner_key_id` + `project_id` through the full planner/executor call chain — confirm
      Gateway REST/MCP auth is live first; this phase cannot start without it.
- [ ] Checkpoint: two different API keys connecting GitHub separately get two different vault rows
      and two different tokens used in practice, verified with two real accounts that have access
      to different repos.

### Phase 4 — Project allocation
- [ ] Implement `GET/PUT /integrations/{source_id}/projects`.
- [ ] Confirm default allocation is empty on connect (not "all projects"), per §2's rule.
- [ ] Confirm planner correctly skips a connected-but-unallocated source with the
      `SourceNotAllocatedError` path from Phase 3.
- [ ] Checkpoint: connect a source, confirm it is queried in zero projects until explicitly
      allocated, then confirm it's queried only in the projects actually checked.

### Phase 5 — Token refresh and expiry
- [ ] Flag credentials `expired` past `expires_at`; attempt silent refresh where a refresh token
      exists before giving up.
- [ ] Flip to `error` immediately on a live 401 from the provider, not just on the next scheduled
      check.
- [ ] Surface status accurately through `GET /integrations` so mobile's "Needs attention" pill is
      always trustworthy.
- [ ] Checkpoint: force an expiry and a live 401 independently, confirm both are reflected correctly
      and promptly.

### Phase 6 — Mobile: Integrations list and connect flows
- [ ] Build the Integrations list screen per §6.2, reading real status per row.
- [ ] Build the device-flow sheet per §6.3 (code, copy, open-link, polling status).
- [ ] Build the auth-code sheet per §6.3 (explainer, in-app browser tab, waiting state, manual
      fallback check button, background polling).
- [ ] Checkpoint: complete a real GitHub connection and a real Jira or Slack connection end to end
      on a physical device with zero manual configuration steps outside the app and the provider's
      own consent page.

### Phase 7 — Mobile: Project Allocation and Integration Detail
- [ ] Build the post-connect Project Allocation checklist per §6.4.
- [ ] Build Integration Detail per §6.5 (status, reconnect, disconnect, editable project checklist).
- [ ] Add the read-only "Connected integrations" line to the project detail/status view per §6.6.
- [ ] Checkpoint: allocate a connected source to two of three projects, confirm chat queries in the
      third project correctly skip it with the right pipeline-trace wording from §6.7.

### Phase 8 — Security and audit hardening
- [ ] Rate-limit `/connect`, `/status`, and `/callback` endpoints explicitly.
- [ ] Confirm `oauth_states` rows are single-use and cannot be replayed after success or expiry.
- [ ] Confirm no log line anywhere contains a decrypted token value.
- [ ] Confirm audit entries exist for connect/disconnect/reconnect/allocation-change events with
      correct actor attribution.
- [ ] Checkpoint: a security read-through of every endpoint's response payloads and every log
      statement touching credentials, confirming zero leakage under any path including errors.

### Phase 9 — Final verification
- [ ] End-to-end: fresh device, connect GitHub via device flow and Jira via auth-code flow, allocate
      each to a different subset of projects, ask a chat question in each project, confirm the
      right sources appear in each project's live pipeline trace and the wrong ones don't.
- [ ] Confirm a second, independent API key connecting the same providers gets entirely separate
      credentials and allocations from the first, with no cross-contamination in either direction.
- [ ] Confirm disconnecting a source cascades its project allocations away cleanly and the next
      chat query in those projects no longer references it.
- [ ] Final checkpoint: a user can, entirely from their phone, with no CLI step at any point,
      connect any supported integration, decide exactly which of their projects it powers, and trust
      that nobody else's credentials or project choices are ever touched by their own.

---

## 10. Mobile-Native Authorization and Allocation System Design Addendum

This addendum formalizes the complete user-centric integration system that the mobile app and Gateway must build together. It keeps the earlier rule intact: mobile is the user's full setup path, while Gateway remains the only trusted server-side component that owns provider secrets, vault encryption, MCP execution, and cross-project enforcement.

### 10.1 Third-party authorization handshake

Every provider connect flow starts from the same authenticated mobile action:

```text
Mobile -> Gateway: POST /integrations/{source_id}/connect
  headers: authenticated RIP/Gateway API key
  body: { project_id?: optional_return_context }
Gateway -> Mobile: provider-specific connect instruction
```

Device-code providers:

1. Gateway creates a pending connect attempt linked to `owner_key_id`, `source_id`, and optional return context.
2. Gateway requests a device code from the provider using server-held OAuth app registration.
3. Mobile receives `user_code`, `verification_uri`, `device_code`, and `expires_in`.
4. The user completes provider authorization in any browser.
5. Mobile polls `GET /integrations/{source_id}/status?device_code=...`.
6. Gateway exchanges the device code for tokens, fetches an account label when possible, stores encrypted credentials, marks the pending attempt complete, and returns `connected`.
7. Mobile opens the project allocation checklist immediately.

Authorization-code providers:

1. Gateway creates `state`, PKCE verifier/challenge, expiry, and pending attempt for `owner_key_id + source_id`.
2. Gateway returns an `authorize_url` that uses Gateway's HTTPS callback URL, not a mobile custom scheme as the default.
3. Mobile opens the provider consent page in a system browser or in-app browser tab.
4. Provider redirects to `GET /integrations/{source_id}/callback?code=...&state=...` on Gateway.
5. Gateway validates state, expiry, single-use status, source id, owner identity, redirect URI, and PKCE verifier.
6. Gateway exchanges the code using server-held client credentials, stores encrypted token material, deletes or completes the pending state, and renders a static success page.
7. Mobile polls `GET /integrations/{source_id}/status` until it sees `connected`, then opens the project allocation checklist.

API-key/manual-secret providers:

1. Gateway returns `required_fields` metadata: label, help text, secret/non-secret field type, validation behavior, and whether testing is available.
2. Mobile renders a secure form and submits values once to Gateway.
3. Gateway validates the API key against the provider or MCP server when possible.
4. Gateway encrypts the secret fields and stores only masked metadata for future list/detail responses.
5. Mobile opens project allocation after successful storage.

Unauthenticated users:

- If the connect request has no valid user identity, Gateway returns an authentication-required response instead of provider instructions.
- Mobile routes through sign-in/API-key enrollment.
- After successful sign-in, Gateway retries or recreates the pending connect attempt under the resolved `owner_key_id`.
- If provider OAuth is the first sign-in step, callback completion may provision the user/API-key identity before storing the credential, but the stored credential must still be keyed to that final identity.

### 10.2 Credential encryption and storage standards

Credential storage is centralized in Gateway and must follow one standard across OAuth providers, API-key providers, and MCP secret material:

- Encrypt access tokens, refresh tokens, API keys, MCP bearer tokens, stdio environment secrets, and provider client secrets at rest with authenticated encryption.
- Keep `GATEWAY_VAULT_KEY` outside source control and outside database rows; production startup must fail when the vault key is missing or known-default.
- Store personal credentials by `owner_key_id + source_id`; store allocation separately so one credential can be linked to unlimited projects.
- Store shared/admin credentials separately from personal credentials and expose them as organization-managed rows to mobile.
- Persist only non-secret metadata in plain columns: account label, scopes, expiry, provider id, connection status, connected timestamp, last refresh timestamp, and last error category.
- Redact secret values from API responses, logs, audit rows, exceptions, traces, and mobile state snapshots.
- Treat OAuth `state` rows as single-use, short-lived records; rejected, expired, and replayed states must not store credentials.
- Reconnect replaces the encrypted credential row for the same owner/source and preserves project allocation unless the user explicitly changes it.
- Disconnect deletes or revokes the credential and cascades allocation rows for that credential.

### 10.3 MCP server integration requirements

Gateway is the execution boundary for all post-auth source operations:

- Mobile may configure source metadata and submit secrets, but it never opens MCP transports, calls provider APIs directly, or executes stdio commands.
- The source registry must provide a project-aware view: global/protected sources plus project-local sources for the active project.
- Built-in source clients and `DynamicMCPSource` must resolve credentials per request, never at process startup.
- Runtime credential lookup receives `owner_key_id`, `source_id`, `project_id`, and credential scope.
- Before a source is queried, Gateway must confirm the credential is connected and linked to the active project.
- A source not linked to the project raises/returns a clean `SourceNotAllocatedError` path; a missing credential uses `SourceNotConnectedError`; expired or revoked credentials use a needs-reauth path.
- Planner/executor must treat those source states as skips with trace events, not whole-request failures.
- MCP stdio configs are validated as executable plus argument arrays and run only server-side with encrypted env material injected by Gateway.
- Tool discovery and health checks should update source capability/status metadata without exposing secret input or output.

### 10.4 Multi-project allocation logic

Allocation is explicit, unlimited, and user-controlled:

```text
source_credentials(id, owner_key_id, source_id, encrypted_secret...)
source_project_links(id, source_credential_id, project_id)
```

Rules:

- A credential may link to zero, one, many, or all projects visible to that owner.
- New credentials default to zero project links.
- `PUT /integrations/{source_id}/projects` is full-replace for the current user's credential.
- The request body accepts any number of `project_ids`; an empty list is valid.
- Gateway validates every project id is visible/owned by the current user before writing links.
- Allocation is evaluated at query time, not only at connect time.
- Creating a new project does not auto-link existing credentials.
- Deleting a project cascades or removes its allocation links without deleting the credential.
- Disconnecting a credential deletes all of its allocation links.
- Project status views may display connected integrations, but editing allocation remains in Integration Detail to keep one source of truth.

### 10.5 Edge-case state model and in-app guidance

The integration API must return a user-facing `state` and optional `guidance` field for every non-happy path:

- `not_authenticated`: sign in required before connecting sources.
- `not_connected`: connect is available.
- `connected`: credential exists and is healthy.
- `connected_unallocated`: credential exists but is linked to no projects or not this project.
- `needs_reauth`: token expired, revoked, refresh failed, or provider returned unauthorized.
- `server_setup_required`: provider app credentials, public callback URL, or shared credential setup is missing.
- `server_exclusive`: source can run only on Gateway; mobile can configure and allocate it, but cannot execute it locally.
- `manual_intervention_required`: provider cannot support a mobile-safe auth path yet.
- `provider_error`: provider validation or token exchange failed with a safe, redacted explanation.

Mobile must use those states directly for row badges, disabled actions, reconnect prompts, and trace drill-ins.

### 10.6 Acceptance criteria

- A fresh mobile user can authenticate, open Settings -> Integrations, connect a supported OAuth provider, and allocate it to selected projects without any Gateway CLI step.
- A user can enter a source API key on mobile, have Gateway validate/encrypt it, and allocate that source to any number of projects.
- A connected source is not queried for a project until explicitly allocated there.
- Two API-key users connecting the same provider receive isolated encrypted credentials and isolated allocation sets.
- Gateway/MCP never exposes plaintext token/API-key material in responses, logs, trace events, or mobile payloads.
- Chat/context traces clearly distinguish not connected, not allocated, needs reauth, provider failure, and server setup/manual intervention.
