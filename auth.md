# RIP Authentication System — Full Plan

## What We're Building

A proper authentication system where users sign up/login using GitHub or Google OAuth. No passwords. No email verification. Just "Sign in with GitHub" or "Sign in with Google" — one tap, done.

---

## The Architecture

```
Mobile App                    RIP Server                    Database
    │                            │                            │
    │── "Sign in with GitHub" ──→│                            │
    │                            │── Redirect to GitHub ─────→│
    │←─ GitHub asks permission ──│                            │
    │── Approve ────────────────→│                            │
    │                            │←─ GitHub callback + code ──│
    │                            │── Exchange code for token  │
    │                            │── Get GitHub user info     │
    │                            │── Find or create user ────→│ users table
    │                            │── Create session ─────────→│ sessions table
    │←── Return API key + user ──│                            │
    │                            │                            │
    │── All future requests ────→│── Verify API key ─────────→│
    │    (Authorization: Bearer) │                            │
```

---

## Database Tables

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255),
    display_name VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE
);

-- OAuth accounts (links user to provider)
CREATE TABLE user_oauth_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    provider VARCHAR(20) NOT NULL,  -- 'github' or 'google'
    provider_user_id VARCHAR(255) NOT NULL,  -- GitHub user ID or Google sub
    provider_email VARCHAR(255),
    provider_username VARCHAR(255),
    provider_avatar_url TEXT,
    access_token TEXT,  -- encrypted
    refresh_token TEXT, -- encrypted  
    token_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, provider_user_id)
);

-- Sessions (one per login)
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    token_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 of API key
    token_prefix VARCHAR(10) NOT NULL,       -- First 10 chars for display
    device_info TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);
```

---

## API Endpoints

### Auth Endpoints

```
GET  /auth/providers                    — List available login providers
GET  /auth/{provider}/login             — Redirect to GitHub/Google OAuth
GET  /auth/{provider}/callback          — OAuth callback URL
POST /auth/logout                       — Revoke current session
GET  /auth/me                           — Get current user info
GET  /auth/sessions                     — List active sessions
DELETE /auth/sessions/{session_id}      — Revoke a session
```

### User Endpoints

```
GET  /users/me                          — Current user profile
PATCH /users/me                         — Update profile
DELETE /users/me                        — Delete account
```

---

## OAuth Flow — Step by Step

### GitHub OAuth

1. **User taps "Sign in with GitHub"** in mobile app
2. Mobile app calls `GET /auth/github/login`
3. Server generates state (CSRF protection), redirects to `https://github.com/login/oauth/authorize`
4. User approves on GitHub
5. GitHub redirects to `GET /auth/github/callback?code=xxx&state=xxx`
6. Server validates state, exchanges code for access token
7. Server calls `https://api.github.com/user` to get user info
8. Server finds or creates user in database
9. Server generates API key (like current `rip_xxx` format)
10. Server returns API key to mobile app
11. Mobile app stores API key in secure storage
12. All future requests use `Authorization: Bearer rip_xxx`

### Google OAuth

Same flow, different endpoints:
- Authorize: `https://accounts.google.com/o/oauth2/v2/auth`
- Token: `https://oauth2.googleapis.com/token`
- User info: `https://www.googleapis.com/oauth2/v3/userinfo`

---

## Mobile App Changes

### Setup Screen — Before vs After

**Before:** Enter server URL + paste API key manually

**After:**
```
┌──────────────────────────────────────────────┐
│  Welcome to RIP                              │
│                                              │
│  Connect to your server:                      │
│  ┌──────────────────────────────────────────┐│
│  │ http://192.168.31.113:8000               ││
│  └──────────────────────────────────────────┘│
│  [Test Connection]                            │
│                                              │
│  ────────── Sign In ──────────               │
│                                              │
│  ┌──────────────────────────────────────────┐│
│  │ 🐙 Continue with GitHub                  ││
│  └──────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────┐│
│  │ 🇬 Continue with Google                  ││
│  └──────────────────────────────────────────┘│
│                                              │
│  ────────── or ──────────                    │
│                                              │
│  [Enter API Key Manually]                    │
└──────────────────────────────────────────────┘
```

### Sign In Flow in Mobile App

```dart
// When user taps "Continue with GitHub"
Future<void> signInWithGithub() async {
  // 1. Get the OAuth URL from server
  final response = await apiClient.get('/auth/github/login');
  final authUrl = response['url'];
  
  // 2. Open browser for user to approve
  final result = await flutter_appauth.authorize(
    AuthorizationRequest(
      serviceConfiguration: AuthorizationServiceConfiguration(
        authorizationEndpoint: authUrl,
        tokenEndpoint: '${serverUrl}/auth/github/callback',
      ),
      clientId: 'rip-app',
      redirectUrl: 'riplink://oauth/callback',
      scopes: ['user:email'],
    ),
  );
  
  // 3. Exchange code for API key
  final apiKey = await apiClient.exchangeOAuthCode(
    provider: 'github',
    code: result.code,
  );
  
  // 4. Save API key securely
  await secureStorage.write('api_key', apiKey);
  
  // 5. Navigate to chat
  goRouter.go('/chat');
}
```

---

## What Already Exists That We Reuse

| Existing | How We Reuse It |
|----------|----------------|
| `user_oauth_tokens` table | Same pattern — store provider tokens encrypted |
| `api_keys` table | Sessions are API keys with user_id |
| `verify_api_key` middleware | Already checks bearer tokens — just add user lookup |
| `gateway_user_id` function | Already extracts user from API key |
| OAuth bridge code (`core/oauth.py`) | Already handles GitHub OAuth for sources — extend for login |
| `flutter_secure_storage` | Already in pubspec.yaml recommendations |

---

## What Needs Building

| Component | Files | Effort |
|-----------|-------|--------|
| **Users table + migration** | `core/storage/models/user.py`, migration | 0.5 day |
| **OAuth login endpoints** | `server/routers/auth.py` | 1 day |
| **User service** | `core/services/user_service.py` | 0.5 day |
| **Session management** | Extend existing `api_keys.py` | 0.5 day |
| **Mobile sign-in UI** | `setup_screen.dart` → add OAuth buttons | 1 day |
| **Mobile OAuth flow** | `flutter_appauth` integration | 1 day |
| **Mobile secure storage** | Replace shared_prefs for API key | 0.5 day |
| **User profile screen** | `profile_screen.dart` | 0.5 day |
| **Team/workspace basics** | Link users to projects | 1 day |

**Total: ~6 days for full auth system**

---

## The Migration Path (Zero Breakage)

1. Add user tables — existing API keys keep working
2. Add OAuth endpoints — existing API key auth keeps working
3. Add sign-in UI — existing manual API key entry keeps working
4. Link existing API keys to a "system" user
5. Users can migrate: link their existing API key to their GitHub account
6. Eventually: new setups require OAuth, manual keys are for CI/CD only

No existing functionality breaks. No existing API keys stop working. Users upgrade at their own pace.