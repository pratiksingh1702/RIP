# Per-User MCP Source Authentication — Build Plan
## Credential Vault, OAuth Connect Flows, and Mobile Integration

---

## WHY THIS PLAN EXISTS

The Context Gateway currently treats GitHub/Jira/Slack as gateway-wide sources with (almost certainly) one shared token read from `.env` at startup. That works for one person self-hosting their own Gateway. It breaks the moment this becomes multi-tenant — the moment more than one person's agent asks for GitHub context through the same Gateway instance, because there's no way to know *whose* GitHub to call.

This plan replaces "one shared token per source" with "one token per (identity, source) pair," stored encrypted, fetched at call time, never cached across identities.

Read this whole document before writing code. Phase 0 contains a decision that changes the shape of everything after it — do not skip ahead.

---

## PHASE 0 — THE IDENTITY DECISION (BLOCKING, DECIDE BEFORE ANY CODE)

Every credential in the vault has to be keyed to *something*. Right now the Gateway's only concept of "who is asking" is an API key, and API keys today are plausibly provisioned one-per-team, not one-per-person.

**You must pick one of these before Phase 1 starts:**

**Option A — API key IS the identity.** Each API key represents one person. Simple, no new auth system needed, but means teams sharing one API key across multiple developers cannot have separate GitHub connections — they'd all share whoever connected first.

**Option B — Add a lightweight person concept underneath API keys.** An API key belongs to a person; a person can have multiple API keys (e.g. one per device); credentials are keyed to the person, not the key. More correct for teams, but is a real schema addition — a `users` table, and `api_keys.owner_user_id` foreign key — not just a vault table bolted onto what exists.

**Recommendation:** Option A first. It ships faster and is honestly what "one phone = one person" from the mobile plan already assumes. Option B becomes worth doing the moment a single API key needs to represent more than one human being — treat that as a distinct future migration, not something to half-build now.

This plan proceeds assuming **Option A** (`owner_key_id` = the calling API key's id). Every schema and endpoint below can be re-keyed to a `owner_user_id` later without changing the shape of the vault itself — only what column it joins against.

- [ ] Decide and record: Option A or Option B
- [ ] If Option B, stop here and scope that migration separately before continuing

---

## PHASE 1 — THE CREDENTIAL VAULT

### 1.1 Schema

```sql
CREATE TABLE source_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    source_name VARCHAR(50) NOT NULL,        -- 'github', 'jira', 'slack'
    encrypted_token TEXT NOT NULL,           -- Fernet-encrypted access token
    encrypted_refresh_token TEXT,            -- Fernet-encrypted, nullable (not all providers issue one)
    scopes TEXT[] DEFAULT '{}',
    expires_at TIMESTAMPTZ,                  -- null = token does not expire (e.g. GitHub classic PAT/OAuth token)
    last_refreshed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',     -- 'active', 'expired', 'revoked', 'error'
    connected_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(owner_key_id, source_name)
);

CREATE TABLE oauth_states (
    state VARCHAR(64) PRIMARY KEY,           -- random CSRF token, also encodes source_name + owner_key_id
    owner_key_id UUID NOT NULL,
    source_name VARCHAR(50) NOT NULL,
    code_verifier VARCHAR(128),              -- for PKCE-capable providers
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL          -- short-lived, e.g. 10 minutes
);

CREATE INDEX idx_source_credentials_owner ON source_credentials(owner_key_id);
CREATE INDEX idx_oauth_states_expiry ON oauth_states(expires_at);
```

`oauth_states` exists specifically for CSRF protection — every OAuth authorize URL includes a random `state` value; the callback must reject any request whose `state` isn't a live, unexpired row here. Skipping this is a real vulnerability, not a nice-to-have.

- [ ] Add `source_credentials` table + Alembic migration
- [ ] Add `oauth_states` table + Alembic migration
- [ ] Add indexes above

### 1.2 Encryption

Use Fernet (symmetric, authenticated encryption) with a key encryption key (KEK) held outside the database — an environment variable or, ideally, a secrets manager, never committed to the repo.

```python
# gateway/core/vault/crypto.py

from cryptography.fernet import Fernet
import os

def get_fernet() -> Fernet:
    key = os.environ["GATEWAY_VAULT_KEY"]  # 32-byte urlsafe base64 key, generated once, stored outside the repo
    return Fernet(key.encode())

def encrypt_token(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()

def decrypt_token(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()
```

- [ ] Add `gateway/core/vault/crypto.py`
- [ ] Generate `GATEWAY_VAULT_KEY` and document it as a required, secret, non-default env var (mirrors the existing "harden secret management" work already done for API keys — reuse that precedent, don't reinvent it)
- [ ] Add a startup check that refuses to boot if `GATEWAY_VAULT_KEY` is unset in production mode

### 1.3 Vault service

```python
# gateway/core/vault/service.py

async def store_credential(session, owner_key_id, source_name, access_token, refresh_token=None, expires_at=None, scopes=None):
    """Upsert — connecting the same source again replaces the old token."""

async def get_credential(session, owner_key_id, source_name) -> DecryptedCredential | None:
    """Returns None if not connected, expired, or revoked. Decrypts just-in-time, never returns a cached plaintext object beyond the call."""

async def revoke_credential(session, owner_key_id, source_name) -> None:
    """Deletes the row. Does not attempt to call the provider's revoke endpoint (Phase 5 handles that separately, optionally)."""

async def list_credentials(session, owner_key_id) -> list[CredentialSummary]:
    """Returns source_name, status, scopes, expires_at — never the token itself."""
```

- [ ] Add `gateway/core/vault/service.py` with the four functions above
- [ ] Add unit tests: store → get roundtrip decrypts correctly; revoke removes the row; list never leaks a token value

---

## PHASE 2 — OAUTH CONNECT FLOWS (PROVIDER-SPECIFIC)

Not all three providers support the same flow shape. Decide per-provider rather than forcing one pattern everywhere.

### 2.1 GitHub — use Device Flow (no redirect URI needed)

GitHub supports OAuth Device Flow, which is the right fit here specifically because it sidesteps the mobile-app redirect-URI problem entirely — there is no callback URL to host or deep-link.

Flow: Gateway requests a device code from GitHub → shows the user an 8-character code and a URL (`github.com/login/device`) → user enters the code on any browser (does not have to be the phone) → Gateway polls GitHub until the user finishes → GitHub returns the access token → Gateway encrypts and stores it.

```
POST /integrations/github/connect
  → Gateway calls GitHub's device code endpoint
  → returns { user_code: "WDJB-MJHT", verification_uri: "https://github.com/login/device", expires_in: 900 }

Mobile displays that code + link. User completes it on any device, in any browser.

GET /integrations/github/status?device_code=...
  → Gateway polls GitHub's token endpoint in the background
  → once approved, stores the token, returns { status: "connected" }
  → mobile polls this endpoint every few seconds until status flips
```

- [ ] Add `POST /integrations/github/connect` — requests device code, returns user_code + verification_uri
- [ ] Add background poll (or a `GET /integrations/github/status` that polls GitHub inline on each call, simpler to start with) that exchanges the device code for a token once approved
- [ ] On success, call `vault.store_credential(...)`
- [ ] GitHub OAuth tokens from this flow generally don't expire unless revoked — confirm this against GitHub's current docs before assuming it, and set `expires_at` accordingly (likely null)

### 2.2 Jira / Atlassian — standard Authorization Code flow, Gateway-hosted callback

Atlassian's OAuth 2.0 (3LO) requires a real HTTPS redirect URI — device flow is not an option here. The Gateway itself needs a public, stable callback URL; mobile cannot host this.

```
POST /integrations/jira/connect
  → Gateway generates a `state` (stored in oauth_states), builds the Atlassian authorize URL
  → returns { authorize_url: "https://auth.atlassian.com/authorize?...&state=..." }

Mobile opens that URL in an in-app browser / system browser.

User approves on Atlassian's own consent screen.

GET /integrations/jira/callback?code=...&state=...
  → Gateway verifies `state` exists in oauth_states and hasn't expired (CSRF check)
  → exchanges `code` for access + refresh token
  → stores via vault.store_credential(...)
  → redirects to a simple Gateway-hosted "Connected — you can close this" page
```

Mobile's job after opening the browser is to poll `GET /integrations` (Phase 4) until Jira shows `status: "active"`, since there's no direct way for the browser tab to hand control back to the app without a deep link — which is solvable but not required for a first version.

- [ ] Add `POST /integrations/jira/connect` — generates state, builds authorize URL
- [ ] Add `GET /integrations/jira/callback` — verifies state, exchanges code, stores credential, shows a static success page
- [ ] Add PKCE if Atlassian's OAuth app configuration supports/requires it (check current app registration settings before assuming)

### 2.3 Slack — standard Authorization Code flow, same shape as Jira

Slack also requires a redirect URI and has no device flow. Same pattern as 2.2, different token endpoint and scope set.

- [ ] Add `POST /integrations/slack/connect`
- [ ] Add `GET /integrations/slack/callback`
- [ ] Confirm whether a bot token or a user token is what RIP's Slack source client actually needs — this changes which OAuth scopes to request and which token type gets stored

### 2.4 Shared endpoints (provider-agnostic)

```
GET /integrations
  → list all sources for the calling identity, with status/expiry/scopes, never the token itself

DELETE /integrations/{source_name}
  → revoke_credential(); optionally also call the provider's own token-revocation endpoint if it has one
```

- [ ] Add `GET /integrations`
- [ ] Add `DELETE /integrations/{source_name}`
- [ ] Rate-limit the `/connect` and `/callback` endpoints specifically — these are the most abuse-prone surface in this entire plan

---

## PHASE 3 — SOURCE CLIENT REFACTOR

This is the change that actually makes multi-tenancy real. Every source client stops holding one static token and starts fetching the caller's token per call.

**Before (current, single-tenant shape):**
```python
class GithubClient:
    def __init__(self, token: str):
        self.token = token  # one token, set once at startup

    async def get_open_prs(self, repo: str):
        # uses self.token for every caller, forever
        ...
```

**After:**
```python
class GithubClient:
    async def get_open_prs(self, repo: str, owner_key_id: UUID, session) -> list[PR]:
        credential = await vault.get_credential(session, owner_key_id, "github")
        if credential is None:
            raise SourceNotConnectedError("github")
        # use credential.access_token for THIS call only — never stored on self, never reused across callers
        ...
```

- [ ] Refactor `GithubClient` to fetch-per-call instead of token-at-init
- [ ] Refactor `JiraClient` the same way
- [ ] Refactor `SlackClient` the same way
- [ ] Thread `owner_key_id` through the planner/executor so it reaches the source clients — this means the executor needs to know who's calling, which should already be available from the authenticated request context once Gateway auth exists (see Tier 0 of the mobile plan — this refactor is not possible until that auth work lands, since there's currently no reliable per-caller identity flowing through the pipeline at all)
- [ ] Add a clear, catchable `SourceNotConnectedError` that the planner can turn into "skip this source, note in the response that GitHub isn't connected" rather than a hard failure

**This phase has a hard dependency: Gateway REST/MCP auth (Tier 0 from the mobile plan) must exist first.** Without it, there's no reliable `owner_key_id` to key any of this off of. Do not attempt Phase 3 before that lands.

---

## PHASE 4 — TOKEN REFRESH AND EXPIRY HANDLING

Tokens die. The system needs to notice before it silently returns nothing useful.

- [ ] Add a background check (runs on each `get_credential` call, or as a periodic job) that flags a credential `status = 'expired'` once past `expires_at`
- [ ] For providers with a refresh token (Jira, possibly Slack depending on token type): attempt a silent refresh before giving up; only mark `expired` if refresh itself fails
- [ ] On a 401 from the actual provider API call (not just local expiry check), mark the credential `status = 'error'` immediately — the provider is the ground truth, not just your local clock
- [ ] Surface connection status through `GET /integrations` so mobile can show "reconnect GitHub" instead of a confusing silent gap in results

---

## PHASE 5 — MOBILE APP INTEGRATION

This directly upgrades the "Sources settings screen" from the earlier mobile feature plan — that screen was designed around a simple enable/disable toggle assuming one shared credential. It now needs to become a real per-source connect flow.

- [ ] Replace the GitHub/Jira/Slack toggle switches with a **Connect / Reconnect / Disconnect** button per source
- [ ] GitHub connect flow: show the device code + "Enter this on github.com/login/device," then poll `GET /integrations/github/status` and flip to "Connected" automatically
- [ ] Jira/Slack connect flow: open the authorize URL in the system browser (`url_launcher` in Flutter), then poll `GET /integrations` until status flips, with a manual "I've approved it" refresh button as a fallback for anyone whose browser tab doesn't auto-return
- [ ] Show scopes granted and connected-since date per source, pulled from `GET /integrations`
- [ ] Show a clear "expired — reconnect" state distinct from "never connected," pulled from the `status` field added in Phase 4
- [ ] Disconnect button calls `DELETE /integrations/{source}` with a confirmation dialog

---

## PHASE 6 — SECURITY AND AUDIT TIE-IN

This plan doesn't exist in isolation from the permission/audit system already built.

- [ ] Every connect, disconnect, and credential-fetch event writes an audit log entry through the existing audit logging path — "who connected what, when" belongs in the same trail as "who accessed what context, when"
- [ ] Confirm the vault's `get_credential` call itself is never logged with the decrypted token value — log the source name and owner_key_id, never the secret
- [ ] Rate-limit `/integrations/*/connect` and `/callback` endpoints explicitly (these are new attack surface — OAuth callback endpoints are a classic target for state-fixation and code-interception attacks if rate limiting and state-expiry aren't both enforced)
- [ ] Confirm `oauth_states` rows are actually deleted or expired after use — a reusable `state` value defeats the CSRF protection it exists to provide

---

## VERIFICATION CHECKLIST (RUN IN ORDER)

```
Phase 0
  [ ] Identity decision recorded (Option A confirmed, or Option B scoped separately)

Phase 1
  [ ] Migrations applied: source_credentials, oauth_states tables exist
  [ ] Vault round-trip test passes: store → get returns the original plaintext
  [ ] Vault list never returns a decrypted token value
  [ ] Gateway refuses to start without GATEWAY_VAULT_KEY set

Phase 2
  [ ] GitHub device flow: connect → user_code shown → approve on github.com/login/device → status flips to connected
  [ ] Jira authorize flow: connect → browser redirect → approve → callback stores credential → state cannot be replayed
  [ ] Slack authorize flow: same shape as Jira, verified independently
  [ ] GET /integrations lists all three with correct status
  [ ] DELETE /integrations/{source} removes the row and the source stops being queried

Phase 3
  [ ] Gateway REST/MCP auth (Tier 0 prerequisite) confirmed live before this phase starts
  [ ] Two different API keys connecting GitHub separately get two different tokens in the vault
  [ ] A get_context call from key A never uses key B's GitHub token, verified by testing with two accounts that have access to different repos

Phase 4
  [ ] An artificially expired credential is correctly flagged and either refreshed or marked expired
  [ ] A 401 from the live provider API immediately flips status to 'error', not just on the next scheduled check

Phase 5
  [ ] Mobile Sources screen shows real connect/reconnect/disconnect states, no more static toggles
  [ ] GitHub device code flow completes end-to-end from the phone
  [ ] Jira/Slack browser-based flow completes end-to-end from the phone

Phase 6
  [ ] Audit log contains connect/disconnect events
  [ ] No decrypted token value appears in any log line, anywhere
  [ ] Rate limiting confirmed on /connect and /callback endpoints
  [ ] Reused/expired oauth_states are rejected on replay
```

---

## WHAT NOT TO BUILD IN THIS PASS

- Do not build Option B (person-level identity) unless Phase 0 explicitly calls for it — don't let this plan quietly grow into a full user-account system.
- Do not build automatic token rotation/refresh scheduling as a standalone background worker process in this pass — refresh-on-demand (Phase 4) is sufficient until there's evidence it isn't.
- Do not attempt to support every OAuth provider's PKCE/state nuances speculatively — implement exactly what GitHub, Jira, and Slack require today, and add others only when a real new source is being integrated.
- Do not skip Phase 0 and start writing vault code against an assumed identity model — that's the mistake this plan is specifically structured to prevent.

---

## MOBILE-FIRST NO-CLI SOURCE CONFIGURATION ADDENDUM

This addendum tightens the plan around the current product requirement: mobile is the complete, user-facing configuration path. A user should never need to run `gateway sources`, edit Context Gateway config files, paste credentials into server `.env`, or ask an operator to finish ordinary personal-source setup. The server still owns OAuth app secrets, encryption keys, MCP execution, and runtime source calls; the phone owns only the user's authentication ceremony, source selection, API-key entry where a provider requires it, and project allocation choices.

### A. User-facing integration catalog

The mobile app must render a categorized integration catalog from Gateway data, not a hardcoded three-provider toggle list. The source for this screen is the dynamic source registry plus provider metadata:

- Code and repository: GitHub, GitLab, Bitbucket, local RIP project intelligence.
- Issue and planning: Jira, Linear, Asana.
- Communication: Slack, Microsoft Teams, Discord when supported.
- Documents and knowledge: Notion, Google Drive, Confluence.
- Custom MCP tools: user- or admin-registered streamable HTTP, SSE, and stdio MCP servers.
- Shared/admin sources: server-managed org-wide sources that users can see but not personally authorize.

Each row reports `source_id`, display name, category, icon key, `credential_scope`, `oauth_flow`, current user status, account label, granted scopes, project allocation count, and whether manual or server-side setup is required. Mobile must treat this response as the source of truth.

### B. Mobile authentication and user registration

Before any source can be connected, the app must have a Gateway-recognized user identity. For the current architecture, that means the mobile login/API-key bootstrap creates or resolves the API-key identity used as `owner_key_id`. If the user reaches Settings -> Integrations while unauthenticated:

1. Mobile redirects to the app's normal sign-in/API-key enrollment flow.
2. Gateway validates or creates the user/API-key identity.
3. The app retries the integration action with the authenticated request context.
4. The user never sees a Gateway CLI instruction as part of this path.

Successful provider OAuth can also complete user registration when the integration is the first authenticated action: Gateway binds the callback/device approval to the pending mobile session, creates the API-key/user identity if needed, then stores the source credential against that identity.

### C. Connect flow by credential type

The connect endpoint is provider-agnostic from mobile's perspective:

```text
POST /integrations/{source_id}/connect
  -> device flow: returns user_code, verification_uri, device_code, expires_in
  -> auth_code flow: returns authorize_url, state, poll_url
  -> api_key flow: returns required_fields metadata for the secure in-app form
  -> shared/admin source: returns server_side_required with guidance text
```

Mobile behavior:

- Device flow: show the code, copy action, open-provider action, and poll status until Gateway exchanges the device code and stores the credential.
- Authorization-code flow: open the provider authorization URL in a system browser/in-app browser tab; Gateway owns the callback URL, validates state/PKCE, exchanges the code, stores the credential, and renders a plain success page. Mobile polls status until connected.
- API-key flow: show a secure form based on `required_fields`; submit secrets only to Gateway; Gateway validates the key if possible, encrypts it, and never returns plaintext.
- Shared/admin flow: show clear in-app guidance that this integration requires server/operator setup and cannot be completed from the phone by this user.

### D. Central credential vault contract

Every token, refresh token, API key, MCP bearer token, stdio env secret, and provider credential is stored encrypted in the centralized Gateway vault. Storage requirements:

- Fernet or equivalent authenticated encryption with `GATEWAY_VAULT_KEY` outside the database.
- One credential row per `owner_key_id + source_id` for personal credentials.
- Shared credentials may exist for `credential_scope = shared`, but must not be mixed with personal credentials or silently override them.
- List/detail endpoints return status metadata only: account label, scopes, expiry, connected time, allocation count, and error category; never plaintext secret material.
- Credential writes, reads for execution, reconnects, revokes, and allocation changes emit audit events without logging secret values.

### E. MCP post-authentication operations

After authentication, Gateway's MCP layer becomes the only component that operates the source. Mobile never connects directly to third-party APIs, MCP servers, or stdio processes. Runtime rules:

1. Planner receives `owner_key_id`, `project_id`, and requested source set from the authenticated request.
2. Source registry returns global/protected sources plus project-scoped sources available for that project.
3. MCP/dynamic/built-in source clients resolve the credential just in time for the current `owner_key_id + source_id`.
4. Source clients confirm the credential is allocated to the active `project_id`.
5. If connected and allocated, Gateway performs the source query/tool call server-side.
6. If not connected, not allocated, expired, or server-exclusive, the planner records a clean skip with user-facing guidance instead of failing the whole context request.

### F. Unlimited project allocation

Connecting a source is separate from using it. After any successful connect, mobile immediately opens the project allocation checklist:

- All projects owned/visible to the authenticated user are listed.
- No projects are preselected for a newly connected source.
- The user can select zero, one, many, or all projects.
- `PUT /integrations/{source_id}/projects` replaces the full allocation set.
- A connected-but-unallocated source is valid and inert.
- New projects created later are not auto-allocated; the user opts them in explicitly.

This keeps one credential reusable across unlimited projects without making a provider active in a project the user did not choose.

### G. Edge cases and required guidance

Mobile must surface explicit guidance for cases the phone cannot complete alone:

- Missing provider OAuth app registration or client secret: "Ask the server administrator to enable this provider."
- Gateway lacks a public HTTPS callback URL for auth-code providers: "This provider needs a public Gateway callback before mobile authorization can finish."
- Shared/admin credential source: "Managed by your organization."
- Provider supports no mobile-safe OAuth or API-key path: show manual intervention instructions and disable Connect.
- Credential expired, revoked, or refresh failed: show "Needs attention" and route to Reconnect.
- MCP stdio source requires backend-only process execution: mobile may configure metadata/secrets, but Gateway validates and runs it server-side only.
- Provider/API validation fails: preserve the row as unconnected or error, show the provider reason without exposing secrets.

### H. Delivery checklist for this addendum

- [ ] Implement source-registry-backed categorized integration catalog.
- [ ] Implement mobile auth bootstrap before source connection.
- [ ] Implement device, auth-code, API-key, and shared/admin connect responses.
- [ ] Store all personal credentials in the encrypted vault keyed by `owner_key_id + source_id`.
- [ ] Add immediate post-connect project allocation with zero-project default.
- [ ] Enforce allocation during Gateway/MCP source execution.
- [ ] Emit user-readable trace skips for not connected, not allocated, needs reauth, and manual intervention cases.
- [ ] Verify a user can connect and allocate a source entirely from the phone with no Gateway CLI step.
