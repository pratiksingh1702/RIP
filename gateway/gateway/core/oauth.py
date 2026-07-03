"""OAuth bridge manager for headless Gateway deployments."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlparse
from uuid import UUID

import httpx
import structlog
from sqlalchemy import delete, select

from gateway.core.permissions.models import UserRole
from gateway.storage.audit_store import get_audit_store
from gateway.storage.database import async_session_factory
from gateway.storage.models import OAuthProvider, OAuthToken, PendingOAuthRequest, RegisteredSource
from gateway.storage.source_registry import _crypt, _decrypt, mask_secret

logger = structlog.get_logger(__name__)

PENDING_TTL = timedelta(minutes=10)


@dataclass(slots=True)
class ProviderSeed:
    id: str
    display_name: str
    authorize_url: str
    token_url: str
    revoke_url: str | None
    default_scopes: list[str]
    supports_pkce: bool
    icon_key: str


PROVIDER_SEEDS = [
    ProviderSeed(
        id="github",
        display_name="GitHub",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        revoke_url=None,
        default_scopes=["repo", "read:org"],
        supports_pkce=True,
        icon_key="github",
    ),
    ProviderSeed(
        id="asana",
        display_name="Asana",
        authorize_url="https://app.asana.com/-/oauth_authorize",
        token_url="https://app.asana.com/-/oauth_token",
        revoke_url="https://app.asana.com/-/oauth_revoke",
        default_scopes=["default"],
        supports_pkce=True,
        icon_key="asana",
    ),
    ProviderSeed(
        id="google_drive",
        display_name="Google Drive",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        revoke_url="https://oauth2.googleapis.com/revoke",
        default_scopes=["https://www.googleapis.com/auth/drive.readonly"],
        supports_pkce=True,
        icon_key="google_drive",
    ),
    ProviderSeed(
        id="slack",
        display_name="Slack",
        authorize_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        revoke_url="https://slack.com/api/auth.revoke",
        default_scopes=["channels:history", "search:read"],
        supports_pkce=True,
        icon_key="slack",
    ),
    ProviderSeed(
        id="jira",
        display_name="Jira",
        authorize_url="https://auth.atlassian.com/authorize",
        token_url="https://auth.atlassian.com/oauth/token",
        revoke_url=None,
        default_scopes=["read:jira-work"],
        supports_pkce=True,
        icon_key="jira",
    ),
    ProviderSeed(
        id="linear",
        display_name="Linear",
        authorize_url="https://linear.app/oauth/authorize",
        token_url="https://api.linear.app/oauth/token",
        revoke_url="https://api.linear.app/oauth/revoke",
        default_scopes=["read"],
        supports_pkce=True,
        icon_key="linear",
    ),
    ProviderSeed(
        id="notion",
        display_name="Notion",
        authorize_url="https://api.notion.com/v1/oauth/authorize",
        token_url="https://api.notion.com/v1/oauth/token",
        revoke_url=None,
        default_scopes=["read_content"],
        supports_pkce=False,
        icon_key="notion",
    ),
    ProviderSeed(
        id="salesforce",
        display_name="Salesforce",
        authorize_url="https://login.salesforce.com/services/oauth2/authorize",
        token_url="https://login.salesforce.com/services/oauth2/token",
        revoke_url="https://login.salesforce.com/services/oauth2/revoke",
        default_scopes=["api", "refresh_token"],
        supports_pkce=True,
        icon_key="salesforce",
    ),
]


async def ensure_oauth_providers() -> None:
    """Seed provider metadata, loading client credentials from server env."""
    async with async_session_factory() as session:
        existing = {
            provider.id: provider
            for provider in (await session.execute(select(OAuthProvider))).scalars()
        }
        for seed in PROVIDER_SEEDS:
            env_prefix = f"GATEWAY_OAUTH_{seed.id.upper()}"
            client_id = os.environ.get(f"{env_prefix}_CLIENT_ID", "")
            client_secret = os.environ.get(f"{env_prefix}_CLIENT_SECRET", "")
            redirect_uris = _redirect_uris_from_env(env_prefix)
            provider = existing.get(seed.id)
            if provider is None:
                provider = OAuthProvider(
                    id=seed.id,
                    display_name=seed.display_name,
                    authorize_url=os.environ.get(f"{env_prefix}_AUTHORIZE_URL", seed.authorize_url),
                    token_url=os.environ.get(f"{env_prefix}_TOKEN_URL", seed.token_url),
                    revoke_url=os.environ.get(f"{env_prefix}_REVOKE_URL", seed.revoke_url),
                    client_id=client_id,
                    client_secret=_crypt(client_secret.encode("utf-8")) if client_secret else "",
                    default_scopes=_scopes_from_env(env_prefix, seed.default_scopes),
                    supports_pkce=_bool_from_env(f"{env_prefix}_SUPPORTS_PKCE", seed.supports_pkce),
                    icon_key=seed.icon_key,
                    allowed_redirect_uris=redirect_uris,
                    enabled=bool(client_id and client_secret),
                )
                session.add(provider)
                continue
            provider.display_name = seed.display_name
            provider.authorize_url = os.environ.get(f"{env_prefix}_AUTHORIZE_URL", seed.authorize_url)
            provider.token_url = os.environ.get(f"{env_prefix}_TOKEN_URL", seed.token_url)
            provider.revoke_url = os.environ.get(f"{env_prefix}_REVOKE_URL", seed.revoke_url)
            provider.default_scopes = _scopes_from_env(env_prefix, seed.default_scopes)
            provider.supports_pkce = _bool_from_env(f"{env_prefix}_SUPPORTS_PKCE", seed.supports_pkce)
            provider.icon_key = seed.icon_key
            provider.allowed_redirect_uris = redirect_uris
            if client_id:
                provider.client_id = client_id
            if client_secret:
                provider.client_secret = _crypt(client_secret.encode("utf-8"))
            provider.enabled = bool(provider.client_id and provider.client_secret)
        await session.commit()


async def list_providers() -> list[dict[str, Any]]:
    """Return provider metadata safe for clients."""
    await ensure_oauth_providers()
    async with async_session_factory() as session:
        providers = (
            await session.execute(select(OAuthProvider).order_by(OAuthProvider.display_name))
        ).scalars()
        return [
            {
                "id": provider.id,
                "display_name": provider.display_name,
                "default_scopes": list(provider.default_scopes or []),
                "supports_pkce": provider.supports_pkce,
                "icon_key": provider.icon_key,
                "configured": provider.enabled,
            }
            for provider in providers
        ]


async def initiate_oauth(
    *,
    provider_id: str,
    source_name: str | None,
    domain_hints: list[str],
    redirect_uri: str,
    client_type: str,
    requested_by: str | None = None,
    existing_source_id: str | None = None,
) -> dict[str, Any]:
    """Create a pending request and return a browser authorize URL."""
    await ensure_oauth_providers()
    async with async_session_factory() as session:
        await _expire_pending(session)
        provider = await session.get(OAuthProvider, provider_id)
        if provider is None:
            raise ValueError(f"Unknown OAuth provider: {provider_id}")
        if not provider.enabled:
            raise ValueError(f"{provider.display_name} OAuth is not configured on this Gateway")
        if not _redirect_uri_allowed(provider, redirect_uri, client_type):
            raise ValueError("Redirect URI is not allowed for this provider/client type")

        if existing_source_id:
            source = await _load_source(session, existing_source_id)
            if source is None:
                raise ValueError("Source not found")
            source.enabled = False
            source.health_status = "pending_authorization"
        else:
            source = RegisteredSource(
                name=await _unique_source_name(session, source_name or f"{provider_id}-oauth"),
                kind="mcp",
                transport="http",
                endpoint_url=None,
                auth_type="oauth2",
                domain_hints=domain_hints,
                priority_hint=50,
                enabled=False,
                health_status="pending_authorization",
                protected=False,
                created_by=requested_by or client_type,
            )
            session.add(source)
            await session.flush()

        state = secrets.token_urlsafe(48)
        code_verifier = secrets.token_urlsafe(64) if provider.supports_pkce else None
        pending = PendingOAuthRequest(
            source_id=source.id,
            provider_id=provider.id,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            client_type=client_type,
            requested_by=requested_by,
            status="pending",
            expires_at=datetime.now(UTC) + PENDING_TTL,
        )
        session.add(pending)
        await session.commit()
        await _audit("oauth_initiate", source.name, requested_by, True, provider.id)
        return {
            "authorize_url": _authorize_url(provider, redirect_uri, state, code_verifier),
            "state": state,
            "source_id": str(source.id),
            "expires_at": pending.expires_at.isoformat().replace("+00:00", "Z"),
        }


async def complete_callback(*, state: str, code: str, requested_by: str | None = None) -> dict[str, Any]:
    """Validate state, exchange the code, and activate the source."""
    async with async_session_factory() as session:
        await _expire_pending(session)
        pending = (
            await session.execute(
                select(PendingOAuthRequest).where(PendingOAuthRequest.state == state)
            )
        ).scalar_one_or_none()
        if pending is None or pending.status != "pending":
            raise ValueError("OAuth state is invalid or already used")
        if pending.expires_at <= datetime.now(UTC):
            pending.status = "expired"
            await session.commit()
            raise ValueError("OAuth state expired")
        provider = await session.get(OAuthProvider, pending.provider_id)
        source = await session.get(RegisteredSource, pending.source_id)
        if provider is None or source is None:
            pending.status = "failed"
            await session.commit()
            raise ValueError("OAuth request is no longer valid")

        token_payload = await _exchange_code(provider, pending, code)
        access_token = token_payload.get("access_token")
        if not access_token:
            pending.status = "failed"
            await session.commit()
            raise ValueError("Provider did not return an access token")

        account_label = _account_label(source.name, provider, token_payload)
        token = await session.get(OAuthToken, source.id)
        if token is None:
            token = OAuthToken(
                source_id=source.id,
                provider_id=provider.id,
                access_token=_crypt(str(access_token).encode("utf-8")),
                account_label=account_label,
            )
            session.add(token)
        token.provider_id = provider.id
        token.access_token = _crypt(str(access_token).encode("utf-8"))
        token.refresh_token = _encrypted_or_none(token_payload.get("refresh_token"))
        token.scope = token_payload.get("scope") or " ".join(provider.default_scopes or [])
        token.token_type = token_payload.get("token_type") or "Bearer"
        token.account_label = account_label
        token.expires_at = _expires_at(token_payload)
        token.last_refreshed_at = datetime.now(UTC)
        token.status = "active"
        source.enabled = True
        source.health_status = "ok"
        pending.status = "completed"
        await session.commit()
        await _audit("oauth_callback", source.name, requested_by or pending.requested_by, True, provider.id)
        return {
            "source_id": str(source.id),
            "provider_id": provider.id,
            "account_label": account_label,
            "status": "active",
        }


async def list_pending(requested_by: str | None = None) -> list[dict[str, Any]]:
    """List pending/expired OAuth attempts."""
    async with async_session_factory() as session:
        await _expire_pending(session)
        stmt = select(PendingOAuthRequest).order_by(PendingOAuthRequest.created_at.desc())
        if requested_by:
            stmt = stmt.where(PendingOAuthRequest.requested_by == requested_by)
        rows = (await session.execute(stmt.limit(50))).scalars()
        return [
            {
                "id": str(row.id),
                "source_id": str(row.source_id),
                "provider_id": row.provider_id,
                "state": row.state,
                "client_type": row.client_type,
                "status": row.status,
                "expires_at": row.expires_at.isoformat().replace("+00:00", "Z"),
            }
            for row in rows
            if row.status in {"pending", "expired", "failed"}
        ]


async def reauthorize_source(
    source_id: str,
    *,
    redirect_uri: str,
    client_type: str,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """Restart OAuth for an existing source."""
    async with async_session_factory() as session:
        token = await session.get(OAuthToken, UUID(source_id))
        if token is None:
            raise ValueError("Source does not have OAuth credentials")
        provider_id = token.provider_id
    return await initiate_oauth(
        provider_id=provider_id,
        source_name=None,
        domain_hints=[],
        redirect_uri=redirect_uri,
        client_type=client_type,
        requested_by=requested_by,
        existing_source_id=source_id,
    )


async def revoke_source(source_id: str, requested_by: str | None = None) -> dict[str, Any]:
    """Revoke provider token if possible and disable the local source."""
    async with async_session_factory() as session:
        source = await _load_source(session, source_id)
        if source is None:
            raise ValueError("Source not found")
        token = await session.get(OAuthToken, source.id)
        if token is None:
            raise ValueError("Source does not have OAuth credentials")
        provider = await session.get(OAuthProvider, token.provider_id)
        if provider is not None and provider.revoke_url:
            try:
                await _call_revoke(provider, token)
            except Exception as exc:
                logger.warning("OAuth revoke request failed", source=source.name, error=str(exc))
        await session.delete(token)
        source.enabled = False
        source.health_status = "revoked"
        await session.commit()
        await _audit("oauth_revoke", source.name, requested_by, True, token.provider_id)
        return {"status": "revoked", "source_id": str(source.id)}


async def refresh_due_tokens() -> None:
    """Refresh active tokens that are close to expiry."""
    now = datetime.now(UTC)
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(OAuthToken).where(
                    OAuthToken.status == "active",
                    OAuthToken.expires_at.is_not(None),
                    OAuthToken.expires_at <= now + timedelta(minutes=10),
                )
            )
        ).scalars()
        for token in rows:
            provider = await session.get(OAuthProvider, token.provider_id)
            source = await session.get(RegisteredSource, token.source_id)
            if provider is None or source is None or not token.refresh_token:
                token.status = "needs_reauth"
                if source is not None:
                    source.enabled = False
                    source.health_status = "needs_reauth"
                continue
            try:
                payload = await _refresh_token(provider, token)
                token.access_token = _crypt(str(payload["access_token"]).encode("utf-8"))
                if payload.get("refresh_token"):
                    token.refresh_token = _crypt(str(payload["refresh_token"]).encode("utf-8"))
                token.expires_at = _expires_at(payload)
                token.last_refreshed_at = now
                await _audit("oauth_refresh", source.name, None, True, provider.id)
            except Exception as exc:
                logger.warning("OAuth refresh failed", source=source.name, error=str(exc))
                token.status = "needs_reauth"
                source.enabled = False
                source.health_status = "needs_reauth"
                await _audit("oauth_refresh", source.name, None, False, str(exc))
        await session.commit()


async def mark_needs_reauth(source_id: str) -> None:
    """Mark an OAuth source unusable after an auth failure."""
    async with async_session_factory() as session:
        source = await _load_source(session, source_id)
        if source is None:
            return
        token = await session.get(OAuthToken, source.id)
        if token is None:
            return
        token.status = "needs_reauth"
        source.enabled = False
        source.health_status = "needs_reauth"
        await session.commit()


def _redirect_uris_from_env(env_prefix: str) -> list[str]:
    raw = os.environ.get(f"{env_prefix}_REDIRECT_URIS", "riplink://oauth/callback")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _scopes_from_env(env_prefix: str, defaults: list[str]) -> list[str]:
    raw = os.environ.get(f"{env_prefix}_SCOPES")
    return [item.strip() for item in raw.split(",") if item.strip()] if raw else defaults


def _bool_from_env(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def _redirect_uri_allowed(provider: OAuthProvider, redirect_uri: str, client_type: str) -> bool:
    parsed = urlparse(redirect_uri)
    if client_type == "cli":
        return parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.path == "/callback"
    return redirect_uri in set(provider.allowed_redirect_uris or [])


def _authorize_url(
    provider: OAuthProvider,
    redirect_uri: str,
    state: str,
    code_verifier: str | None,
) -> str:
    params = {
        "client_id": provider.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    if provider.default_scopes:
        params["scope"] = " ".join(provider.default_scopes)
    if provider.supports_pkce and code_verifier:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    joiner = "&" if "?" in provider.authorize_url else "?"
    return f"{provider.authorize_url}{joiner}{urlencode(params)}"


async def _exchange_code(
    provider: OAuthProvider,
    pending: PendingOAuthRequest,
    code: str,
) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": pending.redirect_uri,
        "client_id": provider.client_id,
        "client_secret": _decrypt(provider.client_secret),
    }
    if pending.code_verifier:
        data["code_verifier"] = pending.code_verifier
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            provider.token_url,
            data=data,
            headers={"Accept": "application/json"},
        )
    response.raise_for_status()
    return response.json()


async def _refresh_token(provider: OAuthProvider, token: OAuthToken) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": _decrypt(token.refresh_token or ""),
        "client_id": provider.client_id,
        "client_secret": _decrypt(provider.client_secret),
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(provider.token_url, data=data, headers={"Accept": "application/json"})
    response.raise_for_status()
    return response.json()


async def _call_revoke(provider: OAuthProvider, token: OAuthToken) -> None:
    data = {
        "token": _decrypt(token.access_token),
        "client_id": provider.client_id,
        "client_secret": _decrypt(provider.client_secret),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(provider.revoke_url or "", data=data, headers={"Accept": "application/json"})
    response.raise_for_status()


def _encrypted_or_none(value: Any) -> str | None:
    return _crypt(str(value).encode("utf-8")) if value else None


def _expires_at(payload: dict[str, Any]) -> datetime | None:
    expires_in = payload.get("expires_in")
    if expires_in is None:
        return None
    try:
        return datetime.now(UTC) + timedelta(seconds=int(expires_in))
    except (TypeError, ValueError):
        return None


def _account_label(source_name: str, provider: OAuthProvider, payload: dict[str, Any]) -> str:
    for key in ("account_label", "team_name", "workspace_name", "name", "login", "email"):
        value = payload.get(key)
        if value:
            return f"{value} ({provider.display_name})"
    return f"{source_name} ({provider.display_name})"


async def _unique_source_name(session, requested: str) -> str:
    base = requested.strip().lower().replace(" ", "-") or "oauth-source"
    existing = {
        row[0]
        for row in (await session.execute(select(RegisteredSource.name))).all()
    }
    if base not in existing:
        return base
    suffix = 2
    while f"{base}-{suffix}" in existing:
        suffix += 1
    return f"{base}-{suffix}"


async def _load_source(session, source_id_or_name: str) -> RegisteredSource | None:
    try:
        source_uuid = UUID(source_id_or_name)
        stmt = select(RegisteredSource).where(RegisteredSource.id == source_uuid)
    except ValueError:
        stmt = select(RegisteredSource).where(RegisteredSource.name == source_id_or_name)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _expire_pending(session) -> None:
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(PendingOAuthRequest).where(
                PendingOAuthRequest.status == "pending",
                PendingOAuthRequest.expires_at <= now,
            )
        )
    ).scalars()
    for row in rows:
        row.status = "expired"
    await session.execute(
        delete(PendingOAuthRequest).where(
            PendingOAuthRequest.status.in_(["completed", "expired", "failed"]),
            PendingOAuthRequest.expires_at <= now - PENDING_TTL,
        )
    )


async def _audit(
    action: str,
    source: str,
    user_id: str | None,
    allowed: bool,
    reason: str | None = None,
) -> None:
    await get_audit_store().log_access(
        session_id="oauth",
        role=UserRole.DEVELOPER,
        action=action,
        allowed=allowed,
        user_id=user_id,
        source=source,
        reason=reason,
    )


def token_mask_for_payload(token: OAuthToken | None) -> str | None:
    """Return a safe token mask for diagnostics and tests."""
    if token is None:
        return None
    return mask_secret(_decrypt(token.access_token))
