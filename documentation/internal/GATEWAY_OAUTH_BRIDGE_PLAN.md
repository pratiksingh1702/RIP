# RIP Gateway — OAuth Bridge: Full Infra-to-UX Plan

**Hand this file to the build agent as-is.** It covers making OAuth-protected MCP servers
(Asana, GitHub private scopes, Google Drive, Slack, Jira, Linear, Notion, Salesforce, and anything
else that speaks OAuth2) addable from the phone or CLI, even though the Gateway itself runs
headless with no browser of its own.

This is Plan 4. It builds directly on the first three and must not contradict them:

- `RIP_GATEWAY_UNIFIED_PLAN.md` — one server connection, one API key, Gateway mounted inside RIP's
  app. Every OAuth endpoint below is mounted there too.
- `CHAT_LIVE_PROGRESS_UX_PLAN.md` — the live pipeline trace. An OAuth-connected source appears in
  that trace exactly like any other source, no special-casing.
- `GATEWAY_SETTINGS_MCP_MOBILE_PLAN.md` — the dynamic source registry and Add Source flow. OAuth is
  not a new screen — it's a new *auth type* inside the Add Source flow that plan already defines.
  A source row's `auth_type` field, previously `api_key`-only in practice, now also supports
  `oauth2`.

---

## 0. The problem, precisely

The Gateway is a headless server process. It has no browser, no user sitting in front of it, and no
way to receive a redirect from an OAuth provider on its own. Every OAuth-protected MCP server
(Asana, private GitHub scopes, Google Drive, Slack with real scopes, Jira, Linear, Notion,
Salesforce) requires a human to click "Allow" in a browser and a redirect to land somewhere that can
capture the resulting authorization code. The Gateway has neither the browser nor, in many
self-hosted deployments, a stable public HTTPS URL a provider will accept as a redirect target.

**The fix is not to give the Gateway a browser.** It's to make the *client* (phone or CLI, both of
which already have a browser and are already the ones initiating the request) responsible for
completing the redirect, while the Gateway stays the only party that ever holds a real token.

---

## 1. Architecture overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Context Gateway (headless, no browser)            │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                        OAuth Manager                          │   │
│  │                                                                │   │
│  │  • Provider Registry     (per-provider app credentials,       │   │
│  │                            authorize/token/revoke URLs,       │   │
│  │                            default scopes, PKCE support)      │   │
│  │  • Pending Request Store (state, PKCE verifier, redirect      │   │
│  │                            target, TTL ~10 min)                │   │
│  │  • Token Store           (encrypted access + refresh tokens,  │   │
│  │                            per source row)                    │   │
│  │  • Refresh Scheduler     (proactive refresh before expiry,    │   │
│  │                            marks needs_reauth on failure)      │   │
│  │  • Callback Endpoint     (exchanges code → token, the only    │   │
│  │                            place a client secret is used)      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                   │                                   │
│  ┌────────────────────────────────┼────────────────────────────┐    │
│  │              MCP Source Adapters (from Plan 3's registry)     │    │
│  │                                                                │    │
│  │   RIP (api_key, always-on)   GitHub (oauth2)  Asana (oauth2)  │    │
│  │   Jira (oauth2)  Slack (oauth2)  Linear (oauth2)  ...         │    │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
             ▲                                          ▲
             │ code + state (after user authorizes)     │
             │                                          │
   ┌─────────┴─────────┐                    ┌──────────┴──────────┐
   │   Mobile App        │                    │   CLI (gateway oauth)│
   │  captures redirect   │                    │  captures redirect   │
   │  via custom URL      │                    │  via localhost       │
   │  scheme, forwards     │                    │  loopback listener   │
   │  code to Gateway     │                    │  forwards code       │
   └───────────────────────┘                    └───────────────────────┘
```

**Core design decision:** the Gateway holds the OAuth app registration (client_id + client_secret)
for each provider — that is a one-time, server-operator setup step, not something end users do from
their phone. What a user does from their phone is *authorize a connection using that already-
registered app* — the same distinction as "an app is published on the App Store once; a user signs
into it many times." Mobile/CLI never see the client secret; they only ever relay an authorization
code.

**Core design decision #2 — redirect target differs by client, callback handling doesn't:**
- **Mobile** uses a custom URL scheme (`riplink://oauth/callback`) as the `redirect_uri`. The OAuth
  provider redirects straight to the phone — this works identically whether the Gateway is on
  `localhost`, a LAN IP, or a public domain, because the provider never needs to reach the Gateway
  directly during the redirect step.
- **CLI** uses a short-lived `http://127.0.0.1:{ephemeral_port}/callback` loopback listener — the
  traditional, provider-accepted CLI OAuth pattern.
- **Both** end the same way: the client POSTs `{code, state}` to the Gateway's one callback
  endpoint, and the Gateway does the actual code-for-token exchange server-side. The capture
  mechanism is client-specific; the exchange logic is written once.

---

## 2. Data model

```sql
-- One row per provider the Gateway's operator has registered an OAuth app for.
-- Not user-editable from mobile; seeded via server config/env, listed read-only in-app.
oauth_providers (
  id              text primary key,       -- 'github', 'asana', 'google_drive', ...
  display_name    text,
  authorize_url   text,
  token_url       text,
  revoke_url      text null,
  client_id       text,
  client_secret   text,                   -- encrypted at rest, never sent to any client
  default_scopes  text[],
  supports_pkce   boolean,
  icon_key        text                    -- maps to a bundled brand icon in the app
)

-- One row per in-flight authorization attempt. TTL-expired rows are purged.
pending_oauth_requests (
  id              uuid primary key,
  source_id       uuid references sources(id),   -- provisional row created at Add Source time
  provider_id     text references oauth_providers(id),
  state           text unique,             -- random nonce, validated on callback
  code_verifier   text,                    -- PKCE, null if provider doesn't support it
  redirect_uri    text,                    -- the exact one used for this attempt (mobile scheme or CLI loopback)
  requested_by    text,                    -- which API key/device initiated it
  status          text,                    -- pending | completed | expired | failed
  created_at      timestamptz,
  expires_at      timestamptz              -- created_at + 10 minutes
)

-- One row per authorized connection. Extends the Plan 3 `sources` table via source_id.
oauth_tokens (
  source_id         uuid primary key references sources(id),
  access_token      bytea,                 -- encrypted
  refresh_token     bytea null,             -- encrypted, null if provider doesn't issue one
  scope             text,
  account_label     text,                  -- "acme-corp (GitHub org)", "jane@company.com (Asana)"
  expires_at        timestamptz,
  last_refreshed_at timestamptz,
  status            text                   -- active | needs_reauth | revoked
)
```

`sources.auth_type` (from Plan 3) gains a new value: `oauth2`, alongside the existing `api_key` and
`none` (for RIP itself). A source row with `auth_type = oauth2` has no directly-stored credential —
its credential lives in `oauth_tokens`, one-to-one.

---

## 3. Backend endpoints

All mounted on the same unified server as everything else.

```
GET    /gateway/oauth/providers                    # list available providers (from oauth_providers,
                                                     # operator-configured — read-only to clients)
POST   /gateway/oauth/initiate                      # body: { provider_id, source_name, domain_hints,
                                                     #         redirect_uri, client_type: mobile|cli }
                                                     # → creates provisional source row (auth_type=oauth2,
                                                     #   enabled=false) + pending_oauth_requests row
                                                     # → returns { authorize_url, state } for the
                                                     #   client to open in a browser
POST   /gateway/oauth/callback                      # body: { state, code }
                                                     # → validates state + TTL, exchanges code for
                                                     #   tokens using stored client_secret + PKCE
                                                     #   verifier, writes oauth_tokens, flips the
                                                     #   provisional source row to enabled=true,
                                                     #   returns { source_id, account_label, status }
GET    /gateway/oauth/pending                       # list this device's in-flight/expired attempts
                                                     # (for the "waiting for authorization" UI state)
POST   /gateway/sources/{id}/oauth/reauthorize       # re-run initiate for an existing source whose
                                                     # token is needs_reauth (keeps the same source
                                                     # row/name/domain hints, just refreshes tokens)
POST   /gateway/sources/{id}/oauth/revoke            # calls provider revoke_url if available,
                                                     # deletes the oauth_tokens row, disables the
                                                     # source (does not delete the source row itself
                                                     # — same "Remove Source" flow from Plan 3 handles
                                                     # full deletion separately)
```

### 3.1 Initiate → authorize → callback sequence

```
1. Client (mobile/CLI) → POST /gateway/oauth/initiate
     { provider_id: "asana", source_name: "Asana", domain_hints: ["planning"],
       redirect_uri: "riplink://oauth/callback", client_type: "mobile" }

2. Gateway → creates provisional source (enabled=false) + pending_oauth_requests
             (state=random, code_verifier=random if PKCE) →
     returns { authorize_url: "https://app.asana.com/-/oauth_authorize?client_id=...
                &redirect_uri=riplink://oauth/callback&state=...&code_challenge=...",
               state: "..." }

3. Client → opens authorize_url in an in-app browser tab (Custom Tabs / SFSafariViewController-
             equivalent — never a raw WebView, so the user sees the real provider domain in the
             address bar and the OS's normal password-manager/2FA integrations still work)

4. User → logs in / clicks Allow on the *provider's own page*, not anything Gateway-branded

5. Provider → redirects to riplink://oauth/callback?code=...&state=...
     Mobile OS hands this back to the RIP app via its registered URL scheme.
     (CLI equivalent: redirects to http://127.0.0.1:{port}/callback?code=...&state=...,
      captured by the CLI's short-lived local listener.)

6. Client → POST /gateway/oauth/callback { state, code }

7. Gateway → validates state exists, not expired, matches a pending request →
             exchanges code + code_verifier for tokens at the provider's token_url
             (this is the one request that includes client_secret, entirely server-side) →
             stores encrypted tokens, flips source to enabled=true →
             returns { source_id, account_label: "acme-corp (Asana workspace)", status: "active" }

8. Client → shows success, source now appears in Settings → Sources exactly like any other source
```

---

## 4. Token lifecycle

- **Refresh scheduler**: a background job checks tokens nearing `expires_at` (e.g. within a
  10-minute window) and proactively refreshes using the stored refresh token — sources should
  essentially never hit a hard expiry mid-query if the scheduler is healthy.
- **On-demand refresh fallback**: if the executor hits a 401 from a source mid-query anyway, it
  attempts one refresh-and-retry before treating the source as failed for that call (this reuses
  the same retry/backoff machinery Plan 3 already generalized — refresh-and-retry is just one more
  reason a call gets retried once, not a separate code path).
- **Refresh failure → `needs_reauth`**: if the refresh token itself is rejected (revoked externally,
  provider requires re-consent, etc.), the source flips to `status: needs_reauth`. It stays in the
  registry (not silently deleted), stops being queried by the planner, and surfaces a clear
  "Needs re-authorization" state everywhere the source appears — Sources list, Source Detail, and
  the live pipeline trace (a `source_skipped` event with `detail: "Asana — needs re-authorization"`,
  same muted-amber treatment as a circuit-broken source from Plan 2).
- **Revocation**: user-initiated "Disconnect" calls the provider's revoke endpoint when available,
  then deletes the local token row — the Gateway does not silently keep a token around "just in
  case" after a user disconnects it.

---

## 5. Security requirements (non-negotiable)

1. **PKCE for every provider that supports it.** Even though the Gateway (a confidential client)
   holds the client secret, the authorization code transits through a mobile app process — PKCE
   adds defense in depth against a code being intercepted or replayed on-device.
2. **State/nonce validation is mandatory and single-use.** A `pending_oauth_requests` row is marked
   `completed` immediately on first successful callback use; a replayed callback with the same state
   is rejected.
3. **10-minute TTL on pending requests.** An abandoned authorization attempt (user backgrounds the
   app, changes their mind) expires and is purged rather than lingering as a valid target forever.
4. **Redirect URI allowlist per provider**, validated server-side against exactly what was issued
   at `initiate` time — the callback endpoint refuses to exchange a code if the redirect_uri on
   record doesn't match what the provider was told to use.
5. **Tokens encrypted at rest**, reusing the same secret-handling mechanism the production-hardening
   pass already established for Gateway's other credentials (Plan 3, §2.4) — one encryption pattern
   for all secrets in the system, not a second one invented for OAuth specifically.
6. **Tokens never leave the Gateway.** Mobile/CLI receive `account_label` and `status` in every
   response — never the access or refresh token itself, not even once, not even right after
   exchange.
7. **Client secrets never leave the Gateway.** `GET /gateway/oauth/providers` returns only what a
   client needs to build the initiate request (provider id, display name, icon) — never client_id
   or client_secret details beyond what's already public in the provider's own authorize URL.
8. **Audit logging.** Every initiate, successful callback, refresh, reauth, and revoke is written to
   the same audit trail Plan 3 already extended to cover dynamic sources — "who authorized what,
   when" is a compliance-relevant event, not just an operational one.

---

## 6. Provider catalog (initial set)

| Provider | Scopes needed (typical) | PKCE | Notes |
|---|---|---|---|
| GitHub | `repo`, `read:org` (only if private/org access needed beyond RIP's own public indexing) | Yes | Public repo search can still go through the existing non-OAuth GitHub source; OAuth unlocks private/org scope |
| Asana | `default` (workspace/task read) | Yes | Workspace selection happens post-auth, surfaced in `account_label` |
| Google Drive | `drive.readonly` | Yes | Read-only scope only — this is a context source, not a write integration |
| Slack | `channels:history`, `search:read` | Yes | Scope carefully — this is the source most likely to over-collect if scopes aren't minimized |
| Jira | `read:jira-work` | Yes | Atlassian OAuth 2.0 (3LO) |
| Linear | `read` | Yes | |
| Notion | `read_content` | No (Notion's OAuth doesn't require PKCE, provider registry marks this per-provider) | |
| Salesforce | `api`, `refresh_token` | Yes | Enterprise/compliance-sensitive — audit logging matters most here |

Each row above becomes an `oauth_providers` seed entry with the operator supplying `client_id`/
`client_secret` via server config (env vars or a server-side admin config file — **not** a mobile
settings screen; see Non-goals).

---

## 7. Mobile UX — integrated into Plan 3's Add Source flow, not a new screen

Recall Plan 3's Add Source flow (§5 of that plan): choose a preset or custom → fill fields → Test
Connection → save. OAuth changes step 2 for providers that require it — nothing else in that flow's
shape changes.

### 7.1 Preset tile selection (unchanged from Plan 3)
User taps a preset tile (Asana, GitHub, Google Drive, Slack, Jira, Linear, Notion, Salesforce).

### 7.2 Auth-type branch (new)
The app already knows from `GET /gateway/oauth/providers` (cross-referenced with the preset)
whether this provider is OAuth or API-key. If OAuth:

- The credential text field from Plan 3 does **not** appear.
- Instead: a single **"Connect with {Provider}"** button, provider-branded per standard OAuth
  button guidelines (correct logo, correct minimum sizing — reuse each provider's published brand
  assets, don't reskin them).
- Domain hint chips (from Plan 3) still appear above the button — those are RIP's own metadata, not
  part of the OAuth exchange, and can be set before or after connecting.

### 7.3 Authorization in progress
- Tapping "Connect with {Provider}" calls `POST /gateway/oauth/initiate`, then opens the returned
  `authorize_url` in the platform's in-app browser tab (Chrome Custom Tabs on Android, matching
  what a production-grade app is expected to use — never an embedded WKWebView/WebView for this,
  both for user trust and because some providers block login inside generic webviews).
- The Add Source sheet shows a waiting state underneath — a determinate-feeling but actually
  indeterminate "Waiting for authorization…" row with a cancel option, not a spinner with no
  context. If the user backgrounds the browser and returns to RIP without finishing, this state
  persists (backed by `GET /gateway/oauth/pending`) until they either finish or cancel.
- The moment the OS delivers the `riplink://oauth/callback?...` deep link back to the app (this can
  happen seconds or minutes later, browser tab or app-switch either way), the app immediately
  extracts `code`/`state`, calls `POST /gateway/oauth/callback`, and transitions the sheet to a
  success or failure state without requiring the user to manually return to the Add Source screen
  themselves — the deep link *is* the return path.

### 7.4 Outcomes
- **Success**: sheet shows "{Provider} connected as {account_label}", auto-dismisses into the
  Sources list where the new row appears live, exactly like a Plan-3 API-key source.
- **User denied on provider's page**: provider redirects back with an error param instead of a
  code; app shows "Authorization was cancelled" with a Try Again button, no error jargon.
- **State mismatch / expired (10+ min elapsed)**: "This authorization link expired. Try again" —
  clear, no technical detail, one retry action.
- **Network failure during callback POST**: standard retry affordance, pending request stays valid
  server-side until its TTL, so retrying doesn't require restarting the whole OAuth dance from
  scratch as long as it's within the window.

### 7.5 Source Detail screen extensions (extends Plan 3's Source Detail)
For an `oauth2` source, Source Detail shows, in place of the Plan-3 "Replace Credential" row:
- **Connected as**: `account_label`, with the provider icon
- **Status badge**: Active / Needs re-authorization / Revoked — same `StatusBadge` component as
  everywhere else in the app
- **Re-authorize** button — only shown/enabled when status is `needs_reauth`; runs the same flow as
  §7.2–7.3 against the existing source row rather than creating a new one
- **Disconnect** button — same destructive-confirm pattern as Plan 3's Remove Source
  ("Disconnect Asana (acme-corp)? RIP will stop checking it in every answer."), calls
  `POST /gateway/sources/{id}/oauth/revoke`

### 7.6 Sources list badge for pending/needs-reauth
The Sources list (Plan 3, §4) already shows a health dot per row. Extend its states to include:
`connected` (green), `needs_reauth` (amber, with a one-tap shortcut straight into Re-authorize —
no need to open Source Detail first for this specific action), `pending_authorization` (a subtle
pulsing/neutral state for a source whose OAuth flow was started but not yet completed — this can
happen if the user started the flow, closed the app, and hasn't returned yet).

### 7.7 Why not push notifications for this
The earlier plan deliberately scoped out push notifications for this pass (conflict alerts, TASK.md
"do not build push notifications... until there's a clear signal this is wanted"). The same rule
applies here even though it's tempting for "come back and finish authorizing" nudges — in-app
polling of `GET /gateway/oauth/pending` plus the amber Sources-list badge is enough signal for this
pass. Revisit push only if there's real evidence users are abandoning OAuth flows mid-way and not
noticing on their own.

---

## 8. CLI role

For headless/server-only deployments without the mobile app in the loop:

```
$ gateway oauth list
Providers available:
  asana         (not connected)
  github        (not connected)
  google_drive  (not connected)
Connected sources:
  rip           (api_key, always-on)

$ gateway oauth setup asana
Starting local callback listener on http://127.0.0.1:53214/callback ...
Opening browser for Asana authorization...
If your browser didn't open, visit:
  https://app.asana.com/-/oauth_authorize?client_id=...&redirect_uri=http://127.0.0.1:53214/callback&state=...

Waiting for authorization... (this will time out in 10 minutes)
✅ Connected: Asana (acme-corp workspace)

$ gateway oauth reauthorize slack
... (same flow, targets the existing source row)

$ gateway oauth revoke slack
Disconnect Slack (acme-corp)? This stops Gateway from querying it. [y/N]
✅ Disconnected.
```

Matches the existing `repo api-keys` / `gateway sources` command style already established —
same verb-noun shape, same confirm-before-destructive pattern, no new CLI conventions introduced.

---

## 9. Non-goals

- **No mobile UI for registering a brand-new OAuth app/client with a provider.** Creating a
  GitHub OAuth App or a Google Cloud OAuth client is a developer-console action the server operator
  does once, out of band (env vars / server admin config). Mobile only ever *authorizes a
  connection* against an app the operator already registered.
- **No push notifications** for pending/expiring authorizations this pass (§7.7).
- **No write-scope OAuth integrations in this pass** — every provider in the initial catalog (§6)
  uses read-only or read-mostly scopes. Write access (creating Asana tasks, posting Slack messages)
  is meaningfully higher risk and out of scope until there's a specific product reason for it.
- **No cross-server OAuth token sharing.** Tokens are scoped to the single Gateway instance that
  performed the exchange — the multi-server-profile feature from the unified plan does not carry
  OAuth connections between servers; reconnecting is required per server, same as any other source.
- **No in-app OAuth app credential editing** (client_id/secret) — that's `oauth_providers` seed
  data, server-config only, matching the same boundary the original Gateway audit already drew
  around strategy-table and circuit-breaker tuning.

---

## 10. Build plan — Phase 0 to full

### Phase 0 — Provider registry and server-side app registration
- [ ] Add the `oauth_providers` table/seed mechanism per §2, loaded from server config/env, not
      user-editable.
- [ ] Register at least GitHub + Asana as real OAuth apps in a dev environment (client_id/secret in
      env) to have something real to build the rest of this plan against.
- [ ] Checkpoint: `GET /gateway/oauth/providers` returns a real, non-empty list with correct
      `supports_pkce` flags per provider.

### Phase 1 — Pending request store and PKCE
- [ ] Add `pending_oauth_requests` table with TTL purge (scheduled cleanup job or lazy
      expire-on-read, either is fine as long as expired rows are never treated as valid).
- [ ] Implement PKCE `code_verifier`/`code_challenge` generation for providers that support it.
- [ ] Implement `POST /gateway/oauth/initiate` — creates the provisional source row (auth_type=
      oauth2, enabled=false) plus the pending request, returns `authorize_url` + `state`.
- [ ] Checkpoint: hitting `initiate` with a valid provider_id returns a real, correctly-formed
      authorize URL that a human can paste into a browser and reach the provider's real consent
      screen.

### Phase 2 — Callback and token exchange
- [ ] Implement `POST /gateway/oauth/callback` — validate state (exists, unexpired, single-use),
      exchange code for tokens at the provider's token_url using the stored client_secret + PKCE
      verifier, store encrypted tokens in `oauth_tokens`, flip the source row to enabled=true.
- [ ] Implement redirect URI allowlist validation per §5 item 4.
- [ ] Implement audit log entries for initiate/callback per §5 item 8.
- [ ] Checkpoint: manually complete a full authorize→redirect→callback cycle with a real provider
      using curl/Postman for the callback step, and confirm a working, queryable token results.

### Phase 3 — Token lifecycle
- [ ] Implement the refresh scheduler (proactive refresh within the expiry window).
- [ ] Implement on-demand refresh-and-retry on a 401 from a source mid-query, reusing the existing
      retry/backoff machinery from the executor.
- [ ] Implement `needs_reauth` status transition on refresh failure.
- [ ] Implement `POST /gateway/sources/{id}/oauth/reauthorize` and
      `POST /gateway/sources/{id}/oauth/revoke`.
- [ ] Checkpoint: force a token to near-expiry in a test environment, confirm the scheduler
      refreshes it without any query ever seeing a 401; separately, force a refresh-token rejection
      and confirm the source correctly flips to `needs_reauth` and stops being planned/queried.

### Phase 4 — Executor, planner, permission, audit integration
- [ ] Confirm an `oauth2` source flows through the executor, ranker, permission engine, and audit
      logging identically to an `api_key` source — auth type should be invisible below the OAuth
      Manager layer (this mirrors Plan 3's Phase 2 discipline exactly).
- [ ] Confirm the live pipeline trace renders `needs_reauth` sources as a muted-amber
      `source_skipped` event with the exact reason, same visual language as a circuit-broken source.
- [ ] Checkpoint: one integration test proves a real OAuth-connected source participates correctly
      in a `get_context` call end to end, including appearing in the pipeline trace and the audit
      log.

### Phase 5 — Mobile: Add Source OAuth branch
- [ ] Extend the Add Source flow's preset step to check `auth_type` and branch to the
      "Connect with {Provider}" button per §7.2, replacing the credential field for OAuth presets.
- [ ] Integrate an in-app browser tab component (Custom Tabs-equivalent) for opening
      `authorize_url` — verify it is not a bare WebView.
- [ ] Register the app's custom URL scheme (`riplink://oauth/callback`) and wire deep-link capture
      to extract `code`/`state` and call `POST /gateway/oauth/callback` automatically.
- [ ] Build the "Waiting for authorization…" state backed by `GET /gateway/oauth/pending`, with
      cancel support.
- [ ] Build all four outcome states from §7.4 (success, denied, expired, network failure).
- [ ] Checkpoint: complete a real Asana or GitHub OAuth connection end to end on a physical device,
      confirm the source appears live in Settings → Sources afterward with zero manual steps beyond
      tapping Connect and Allow.

### Phase 6 — Mobile: Source Detail and Sources list OAuth states
- [ ] Extend Source Detail per §7.5: Connected-as label, status badge, Re-authorize, Disconnect.
- [ ] Extend Sources list badges per §7.6: connected / needs_reauth / pending_authorization states,
      with the one-tap Re-authorize shortcut from the list for `needs_reauth` rows.
- [ ] Checkpoint: manually force a source into `needs_reauth` (revoke the token on the provider's
      side directly) and confirm the app surfaces it correctly within one refresh cycle, with a
      working one-tap re-authorize path.

### Phase 7 — CLI parity
- [ ] Implement `gateway oauth list`, `gateway oauth setup <provider>`,
      `gateway oauth reauthorize <source>`, `gateway oauth revoke <source>` per §8, using the
      localhost-loopback capture pattern.
- [ ] Checkpoint: complete a full OAuth connection from a terminal with no mobile app involved,
      confirm the resulting source is indistinguishable from one added via mobile.

### Phase 8 — Security and audit hardening pass
- [ ] Confirm every requirement in §5 is actually true in the shipped code, not just designed —
      specifically: PKCE in use where supported, state single-use enforced, TTL enforced, redirect
      URI allowlist enforced, tokens never appear in any API response body anywhere, client secrets
      never appear in any API response body anywhere.
- [ ] Confirm audit log entries exist for every initiate/callback/refresh/reauth/revoke event with
      correct actor attribution.
- [ ] Checkpoint: a security-focused read-through of every OAuth endpoint's response payloads,
      confirming no token or secret leakage under any response path, including error responses.

### Phase 9 — Design QA and final verification
- [ ] Confirm provider-branded "Connect with {Provider}" buttons use correct, unmodified brand
      assets per each provider's published guidelines.
- [ ] Confirm the Add Source flow's shape is otherwise unchanged from Plan 3 — OAuth is a branch
      inside step 2, not a new flow, not a new screen.
- [ ] Confirm the chat screen is untouched by this entire plan — OAuth connections are configured
      and managed entirely under Settings → Sources, per the same discipline as Plan 3.
- [ ] End-to-end: connect two different OAuth providers, ask a chat question relevant to each
      domain, confirm both appear correctly and independently in the live pipeline trace; then
      revoke one and confirm it stops appearing in subsequent traces while the other keeps working.
- [ ] Final checkpoint: a user can, entirely from their phone, connect Asana or GitHub or any other
      OAuth-protected MCP server without ever seeing a client secret, without the Gateway ever
      needing a browser of its own, and without leaving RIP's single chat screen's one-tap Settings
      entry point — and a server operator with no mobile app at all can do the exact same thing from
      the CLI.
