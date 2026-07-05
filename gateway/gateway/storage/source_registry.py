"""Persistent source registry and Gateway settings helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from itertools import cycle
from uuid import UUID, uuid4

from sqlalchemy import delete, or_, select

from gateway.config import settings
from gateway.storage.database import async_session_factory
from gateway.storage.models import (
    GatewaySetting,
    OAuthProvider,
    OAuthToken,
    RegisteredSource,
    SourceCredential,
    SourceProjectLink,
    UserOAuthToken,
)


@dataclass(slots=True)
class SourceRecord:
    """Serializable registry record used by runtime code."""

    id: str
    name: str
    project_id: str | None
    kind: str
    transport: str
    endpoint_url: str | None
    auth_type: str
    credential_ref: str | None
    credential: str | None
    credential_mask: str | None
    mcp_config: dict
    oauth_provider_id: str | None
    oauth_status: str | None
    oauth_account_label: str | None
    domain_hints: list[str]
    priority_hint: int
    enabled: bool
    health_status: str
    protected: bool
    created_by: str | None
    requires_auth: bool = False
    connected: bool = False
    connectable: bool = False
    allocated_project_ids: list[str] | None = None
    allocation_count: int = 0
    allocated_to_project: bool = False
    integration_state: str = "available"
    guidance: str | None = None
    category: str = "custom"


BUILTIN_SOURCE_DEFAULTS = [
    {
        "name": "rip",
        "kind": "builtin",
        "transport": "stdio",
        "endpoint_url": settings.rip_mcp_cwd,
        "auth_type": "none",
        "mcp_config": {"tool_name": "search"},
        "enabled": True,
        "health_status": "ok",
        "protected": True,
        "priority_hint": 100,
        "domain_hints": ["code", "architecture", "debugging", "docs", "api", "database"],
    },
    {
        "name": "github",
        "kind": "builtin",
        "transport": "http",
        "endpoint_url": settings.github_api_url,
        "auth_type": "bearer" if settings.github_token else "oauth2",
        "mcp_config": {"tool_name": "search"},
        "enabled": settings.github_mcp_enabled if settings.github_token else False,
        "health_status": "unknown",
        "protected": False,
        "priority_hint": 70,
        "domain_hints": ["code", "review", "git", "api"],
    },
    {
        "name": "jira",
        "kind": "builtin",
        "transport": "http",
        "endpoint_url": settings.jira_url or None,
        "auth_type": "bearer" if settings.jira_token else "oauth2",
        "mcp_config": {"tool_name": "search"},
        "enabled": settings.jira_mcp_enabled if settings.jira_token else False,
        "health_status": "unknown",
        "protected": False,
        "priority_hint": 65,
        "domain_hints": ["planning", "tickets", "requirements"],
    },
    {
        "name": "slack",
        "kind": "builtin",
        "transport": "http",
        "endpoint_url": "https://slack.com/api",
        "auth_type": "bearer" if settings.slack_token else "oauth2",
        "mcp_config": {"tool_name": "search"},
        "enabled": settings.slack_mcp_enabled if settings.slack_token else False,
        "health_status": "unknown",
        "protected": False,
        "priority_hint": 55,
        "domain_hints": ["discussion", "docs", "support"],
    },
]


def _secret_key() -> bytes:
    material = (
        settings.google_api_key
        or settings.redis_url
        or settings.postgres_url
        or "rip-gateway-local-secret"
    )
    return hashlib.sha256(material.encode("utf-8")).digest()


def _crypt(value: bytes) -> str:
    key = _secret_key()
    encrypted = bytes(byte ^ key_byte for byte, key_byte in zip(value, cycle(key)))
    digest = hmac.new(key, value, hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{digest}:".encode("ascii") + encrypted).decode("ascii")


def _decrypt(value: str) -> str:
    key = _secret_key()
    raw = base64.urlsafe_b64decode(value.encode("ascii"))
    _, encrypted = raw.split(b":", 1)
    decrypted = bytes(byte ^ key_byte for byte, key_byte in zip(encrypted, cycle(key)))
    return decrypted.decode("utf-8")


def mask_secret(secret: str | None) -> str | None:
    """Return a non-revealing credential mask."""
    if not secret:
        return None
    suffix = secret[-4:] if len(secret) >= 4 else secret
    return f"********{suffix}"


def mask_env(env: dict[str, str] | None) -> dict[str, str]:
    """Mask environment values before returning source config to clients."""
    if not env:
        return {}
    return {key: mask_secret(str(value)) or "********" for key, value in env.items()}


async def ensure_builtin_sources() -> None:
    """Seed protected RIP and configured built-in optional sources."""
    async with async_session_factory() as session:
        existing = {
            source.name: source
            for source in (await session.execute(select(RegisteredSource))).scalars()
        }
        changed = False
        for defaults in BUILTIN_SOURCE_DEFAULTS:
            source = existing.get(defaults["name"])
            if source is None:
                session.add(RegisteredSource(**defaults))
                changed = True
                continue
            source.kind = "builtin"
            source.protected = bool(defaults["protected"])
            source.transport = defaults["transport"]
            source.endpoint_url = defaults["endpoint_url"]
            source.auth_type = defaults["auth_type"]
            source.mcp_config = source.mcp_config or dict(defaults.get("mcp_config") or {})
            if source.name == "rip":
                source.enabled = True
                source.health_status = "ok"
            changed = True
        if changed:
            await session.commit()


async def list_sources(
    *,
    project_id: str | None = None,
    user_id: str | None = None,
    include_global: bool = True,
) -> list[SourceRecord]:
    """Return all registered source rows with decrypted credentials for runtime use."""
    await ensure_builtin_sources()
    async with async_session_factory() as session:
        stmt = select(RegisteredSource).order_by(RegisteredSource.priority_hint.desc())
        if project_id is not None:
            if include_global:
                stmt = stmt.where(
                    (RegisteredSource.project_id == project_id)
                    | (RegisteredSource.project_id.is_(None))
                    | (RegisteredSource.protected.is_(True))
                )
            else:
                stmt = stmt.where(RegisteredSource.project_id == project_id)
        sources = (await session.execute(stmt)).scalars().all()
        credential_refs = [source.credential_ref for source in sources if source.credential_ref]
        for source in sources:
            mcp_config = source.mcp_config or {}
            env_ref = mcp_config.get("stdio_env_ref")
            if env_ref:
                credential_refs.append(env_ref)
        credentials = {}
        if credential_refs:
            result = await session.execute(
                select(SourceCredential).where(SourceCredential.ref.in_(credential_refs))
            )
            credentials = {credential.ref: credential for credential in result.scalars()}
        allocation_map: dict[str, list[str]] = {}
        if user_id:
            token_rows = (
                await session.execute(
                    select(UserOAuthToken).where(
                        UserOAuthToken.source_id.in_([source.id for source in sources]),
                        UserOAuthToken.user_id == user_id,
                        UserOAuthToken.project_id.in_(["", project_id or ""]),
                    )
                )
            ).scalars().all()
            token_ids = [token.id for token in token_rows]
            if token_ids:
                link_rows = (
                    await session.execute(
                        select(SourceProjectLink).where(SourceProjectLink.user_oauth_token_id.in_(token_ids))
                    )
                ).scalars().all()
                token_id_to_source = {token.id: str(token.source_id) for token in token_rows}
                for link in link_rows:
                    source_key = token_id_to_source.get(link.user_oauth_token_id)
                    if source_key:
                        allocation_map.setdefault(source_key, []).append(link.project_id)
        else:
            token_rows = (
                await session.execute(
                    select(OAuthToken).where(OAuthToken.source_id.in_([source.id for source in sources]))
                )
            ).scalars().all()
        oauth_tokens = _token_map(token_rows, project_id=project_id)
        return [
            _record_from_model(
                source,
                credentials.get(source.credential_ref or ""),
                oauth_tokens.get(source.id),
                credentials,
                project_id=project_id,
                allocated_project_ids=allocation_map.get(str(source.id), []),
            )
            for source in sources
        ]


async def get_source(
    source_id_or_name: str,
    *,
    project_id: str | None = None,
    user_id: str | None = None,
) -> SourceRecord | None:
    """Get a source by UUID or name."""
    await ensure_builtin_sources()
    async with async_session_factory() as session:
        stmt = select(RegisteredSource)
        try:
            source_uuid = UUID(source_id_or_name)
            stmt = stmt.where(RegisteredSource.id == source_uuid)
        except ValueError:
            stmt = stmt.where(RegisteredSource.name == source_id_or_name)
        source = (await session.execute(stmt)).scalar_one_or_none()
        if source is None:
            return None
        credential = None
        if source.credential_ref:
            credential = await session.get(SourceCredential, source.credential_ref)
        oauth_token, allocated_project_ids = await _load_oauth_token_for_scope(
            session,
            source.id,
            project_id=project_id,
            user_id=user_id,
        )
        extra_credentials = {}
        env_ref = (source.mcp_config or {}).get("stdio_env_ref")
        if env_ref:
            env_credential = await session.get(SourceCredential, env_ref)
            if env_credential:
                extra_credentials[env_ref] = env_credential
        return _record_from_model(
            source,
            credential,
            oauth_token,
            extra_credentials,
            project_id=project_id,
            allocated_project_ids=allocated_project_ids,
        )


async def create_source(
    *,
    name: str,
    project_id: str | None = None,
    kind: str = "mcp",
    transport: str,
    endpoint_url: str | None,
    auth_type: str = "none",
    credential: str | None = None,
    mcp_config: dict | None = None,
    domain_hints: list[str] | None = None,
    priority_hint: int = 50,
    enabled: bool = True,
    created_by: str | None = None,
) -> SourceRecord:
    """Create a dynamic source row and optional credential."""
    await ensure_builtin_sources()
    async with async_session_factory() as session:
        name_value = name.strip()
        existing = (
            await session.execute(
                select(RegisteredSource).where(
                    RegisteredSource.name == name_value,
                    or_(
                        RegisteredSource.project_id == project_id,
                        RegisteredSource.protected.is_(True),
                        RegisteredSource.kind == "builtin",
                    ),
                )
            )
        ).scalars().first()
        if existing is not None:
            raise ValueError(f"Source name '{name_value}' is already used in this scope")
        source = RegisteredSource(
            name=name_value,
            project_id=project_id,
            kind=kind,
            transport=transport,
            endpoint_url=endpoint_url,
            auth_type=auth_type,
            mcp_config=mcp_config or {},
            domain_hints=domain_hints or [],
            priority_hint=priority_hint,
            enabled=enabled,
            health_status="unknown",
            protected=False,
            created_by=created_by,
        )
        session.add(source)
        await session.flush()
        if credential:
            source.credential_ref = await _store_credential(session, source.id, credential)
        await _store_mcp_env_if_present(session, source, source.mcp_config)
        await session.commit()
        await session.refresh(source)
        stored_credential = await session.get(SourceCredential, source.credential_ref) if source.credential_ref else None
        extra_credentials = {}
        env_ref = (source.mcp_config or {}).get("stdio_env_ref")
        if env_ref:
            env_credential = await session.get(SourceCredential, env_ref)
            if env_credential:
                extra_credentials[env_ref] = env_credential
        return _record_from_model(source, stored_credential, None, extra_credentials)


async def update_source(source_id_or_name: str, updates: dict) -> SourceRecord | None:
    """Patch editable source metadata."""
    async with async_session_factory() as session:
        source = await _load_source_model(session, source_id_or_name)
        if source is None:
            return None
        if source.protected and updates.get("enabled") is False:
            raise ValueError("RIP is always on and cannot be disabled")
        next_name = updates.get("name", source.name)
        next_project_id = updates.get("project_id", source.project_id)
        if next_name != source.name or next_project_id != source.project_id:
            existing = (
                await session.execute(
                    select(RegisteredSource).where(
                        RegisteredSource.id != source.id,
                        RegisteredSource.name == str(next_name).strip(),
                        or_(
                            RegisteredSource.project_id == next_project_id,
                            RegisteredSource.protected.is_(True),
                            RegisteredSource.kind == "builtin",
                        ),
                    )
                )
            ).scalars().first()
            if existing is not None:
                raise ValueError(f"Source name '{next_name}' is already used in this scope")
        for field in ("name", "project_id", "endpoint_url", "auth_type", "transport"):
            if field in updates and updates[field] is not None:
                value = str(updates[field]).strip() if field == "name" else updates[field]
                setattr(source, field, value)
        if "mcp_config" in updates and updates["mcp_config"] is not None:
            merged = dict(source.mcp_config or {})
            merged.update(updates["mcp_config"])
            source.mcp_config = merged
            await _store_mcp_env_if_present(session, source, source.mcp_config)
        if "domain_hints" in updates and updates["domain_hints"] is not None:
            source.domain_hints = updates["domain_hints"]
        if "priority_hint" in updates and updates["priority_hint"] is not None:
            source.priority_hint = updates["priority_hint"]
        if "enabled" in updates and updates["enabled"] is not None:
            source.enabled = bool(updates["enabled"])
        if "health_status" in updates and updates["health_status"] is not None:
            source.health_status = str(updates["health_status"])
        await session.commit()
        await session.refresh(source)
        credential = await session.get(SourceCredential, source.credential_ref) if source.credential_ref else None
        oauth_token = await session.get(OAuthToken, source.id)
        extra_credentials = {}
        env_ref = (source.mcp_config or {}).get("stdio_env_ref")
        if env_ref:
            env_credential = await session.get(SourceCredential, env_ref)
            if env_credential:
                extra_credentials[env_ref] = env_credential
        return _record_from_model(source, credential, oauth_token, extra_credentials)


async def delete_source(source_id_or_name: str) -> bool:
    """Delete a dynamic source unless it is protected."""
    async with async_session_factory() as session:
        source = await _load_source_model(session, source_id_or_name)
        if source is None:
            return False
        if source.protected or source.kind == "builtin":
            raise ValueError(f"{source.name} is a protected source and cannot be removed")
        await session.delete(source)
        await session.commit()
        return True


async def replace_credential(source_id_or_name: str, credential: str) -> SourceRecord | None:
    """Replace a source credential without returning plaintext to clients."""
    async with async_session_factory() as session:
        source = await _load_source_model(session, source_id_or_name)
        if source is None:
            return None
        source.credential_ref = await _store_credential(session, source.id, credential)
        await session.commit()
        await session.refresh(source)
        stored = await session.get(SourceCredential, source.credential_ref)
        oauth_token = await session.get(OAuthToken, source.id)
        extra_credentials = {}
        env_ref = (source.mcp_config or {}).get("stdio_env_ref")
        if env_ref:
            env_credential = await session.get(SourceCredential, env_ref)
            if env_credential:
                extra_credentials[env_ref] = env_credential
        return _record_from_model(source, stored, oauth_token, extra_credentials)


async def replace_user_oauth_credential(
    source_id_or_name: str,
    *,
    user_id: str,
    credential: str,
    provider_id: str | None = None,
) -> SourceRecord | None:
    """Store a mobile-entered API key as the current user's connected source credential."""
    async with async_session_factory() as session:
        source = await _load_source_model(session, source_id_or_name)
        if source is None:
            return None
        provider_key = provider_id or source.name
        provider = await session.get(OAuthProvider, provider_key)
        if provider is None:
            raise ValueError(f"OAuth provider '{provider_key}' is not registered")
        token = await _load_user_source_token(session, source.id, user_id)
        if token is None:
            token = UserOAuthToken(
                source_id=source.id,
                provider_id=provider.id,
                user_id=user_id,
                project_id="",
                access_token=_crypt(credential.encode("utf-8")),
                account_label=f"{source.name} token",
            )
            session.add(token)
        token.provider_id = provider.id
        token.access_token = _crypt(credential.encode("utf-8"))
        token.refresh_token = None
        token.scope = "api_key"
        token.token_type = "Bearer"
        token.account_label = f"{source.name} token"
        token.status = "active"
        source.enabled = True
        source.health_status = "ok"
        await session.commit()
        await session.refresh(source)
        return _record_from_model(
            source,
            None,
            token,
            {},
            project_id=None,
            allocated_project_ids=await _allocation_ids(session, token),
        )


async def get_gateway_settings() -> dict:
    """Return editable Gateway defaults."""
    async with async_session_factory() as session:
        row = await session.get(GatewaySetting, "defaults")
        stored = row.value if row else {}
    # Merge stored settings with defaults from settings class
    defaults = {
        "default_max_tokens": settings.default_max_tokens,
        "overhead_reserve_ratio": settings.overhead_reserve_ratio,
        "min_tokens_per_source": settings.min_tokens_per_source,
        "default_role": settings.default_role,
    }
    # Non-secret source defaults can be persisted here; credentials belong in
    # SourceCredential/OAuthToken rows.
    for key in ["github_repo", "github_api_url", "jira_url", "jira_project_key", "slack_channel_id"]:
        if key in stored:
            defaults[key] = stored[key]
        else:
            # Check if key exists in settings class
            if hasattr(settings, key):
                defaults[key] = getattr(settings, key)
    # Also include any other stored keys
    for key, val in stored.items():
        if key not in defaults:
            defaults[key] = val
    return defaults


async def update_gateway_settings(updates: dict) -> dict:
    """Persist editable Gateway defaults."""
    current = await get_gateway_settings()
    # Apply all updates, not just specific keys
    for key, value in updates.items():
        if value is not None:
            current[key] = value
    async with async_session_factory() as session:
        row = await session.get(GatewaySetting, "defaults")
        if row is None:
            row = GatewaySetting(key="defaults", value=current)
            session.add(row)
        else:
            row.value = current
        await session.commit()
    return current


async def _store_credential(session, source_id, credential: str) -> str:
    ref = f"src_{uuid4().hex}"
    session.add(
        SourceCredential(
            ref=ref,
            source_id=source_id,
            encrypted_value=_crypt(credential.encode("utf-8")),
            masked_value=mask_secret(credential) or "********",
        )
    )
    return ref


async def _store_mcp_env_if_present(session, source: RegisteredSource, mcp_config: dict) -> None:
    """Store stdio environment values write-only and keep only a ref/mask in config."""
    env = mcp_config.pop("stdio_env", None)
    if env is None:
        source.mcp_config = mcp_config
        return
    if not isinstance(env, dict):
        raise ValueError("stdio_env must be an object")
    normalized = {str(key): str(value) for key, value in env.items() if str(key).strip()}
    ref = f"srcenv_{uuid4().hex}"
    session.add(
        SourceCredential(
            ref=ref,
            source_id=source.id,
            encrypted_value=_crypt(json.dumps(normalized).encode("utf-8")),
            masked_value="********",
        )
    )
    mcp_config["stdio_env_ref"] = ref
    mcp_config["stdio_env_mask"] = mask_env(normalized)
    source.mcp_config = mcp_config


async def _load_source_model(session, source_id_or_name: str) -> RegisteredSource | None:
    try:
        source_uuid = UUID(source_id_or_name)
        stmt = select(RegisteredSource).where(RegisteredSource.id == source_uuid)
    except ValueError:
        stmt = select(RegisteredSource).where(RegisteredSource.name == source_id_or_name)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _load_oauth_token_for_scope(
    session,
    source_id,
    *,
    project_id: str | None = None,
    user_id: str | None = None,
):
    if user_id:
        token = await _load_user_source_token(session, source_id, user_id)
        if token is None and project_id:
            token = (
                await session.execute(
                    select(UserOAuthToken).where(
                        UserOAuthToken.source_id == source_id,
                        UserOAuthToken.user_id == user_id,
                        UserOAuthToken.project_id == project_id,
                    )
                )
            ).scalar_one_or_none()
        if token is None:
            return None, []
        return token, await _allocation_ids(session, token)
    return await session.get(OAuthToken, source_id), []


async def _load_user_source_token(session, source_id, user_id: str) -> UserOAuthToken | None:
    """Load the reusable per-user credential row for a source."""
    return (
        await session.execute(
            select(UserOAuthToken).where(
                UserOAuthToken.source_id == source_id,
                UserOAuthToken.user_id == user_id,
                UserOAuthToken.project_id == "",
            )
        )
    ).scalar_one_or_none()


async def _allocation_ids(session, token: UserOAuthToken) -> list[str]:
    rows = (
        await session.execute(
            select(SourceProjectLink.project_id)
            .where(SourceProjectLink.user_oauth_token_id == token.id)
            .order_by(SourceProjectLink.project_id)
        )
    ).scalars().all()
    if rows:
        return [str(row) for row in rows]
    # Compatibility: old user_oauth_tokens rows stored the active project directly.
    return [token.project_id] if token.project_id else []


def _token_map(
    token_rows: list[OAuthToken | UserOAuthToken],
    *,
    project_id: str | None,
) -> dict:
    by_source = {}
    for token in token_rows:
        source_id = token.source_id
        if not isinstance(token, UserOAuthToken):
            by_source[source_id] = token
            continue
        if token.project_id == "":
            by_source[source_id] = token
        elif project_id and token.project_id == project_id and source_id not in by_source:
            by_source[source_id] = token
    return by_source


def _integration_state(
    *,
    source: RegisteredSource,
    requires_auth: bool,
    oauth_token: OAuthToken | UserOAuthToken | None,
    oauth_active: bool,
    project_id: str | None,
    allocated_to_project: bool,
    allocation_count: int,
    server_setup_required: bool,
) -> tuple[str, str | None]:
    if source.protected:
        return "connected", None
    if server_setup_required:
        return "server_setup_required", "Provider authorization is waiting for server-side OAuth setup or completion."
    if requires_auth and oauth_token is None:
        return "not_connected", "Connect this integration from mobile before using it in projects."
    if oauth_token is not None and oauth_token.status != "active":
        return "needs_reauth", "Access expired or was revoked. Reconnect this integration."
    if requires_auth and oauth_active and project_id and not allocated_to_project:
        return "connected_unallocated", "Connected, but not enabled for this project."
    if requires_auth and oauth_active and allocation_count == 0:
        return "connected_unallocated", "Connected, but not enabled for any project yet."
    if requires_auth and oauth_active:
        return "connected", None
    if source.auth_type in {"bearer", "api_key", "token"} and not source.credential_ref:
        return "manual_intervention_required", "Add this source API key from mobile before testing or using it."
    if source.transport == "stdio":
        return "server_exclusive", "This source runs only on Gateway. Mobile can configure it, but Gateway executes it."
    return "available", None


def _source_category(source: RegisteredSource) -> str:
    hints = {hint.lower() for hint in (source.domain_hints or [])}
    name = source.name.lower()
    if name in {"github", "gitlab", "bitbucket"} or {"code", "git", "review"} & hints:
        return "code"
    if name in {"jira", "linear", "asana"} or {"planning", "tickets", "requirements"} & hints:
        return "planning"
    if name in {"slack", "teams", "discord"} or {"discussion", "support"} & hints:
        return "communication"
    if name in {"notion", "google_drive", "confluence"} or {"docs", "knowledge"} & hints:
        return "knowledge"
    if source.kind == "builtin":
        return "builtin"
    return "custom"


def _record_from_model(
    source: RegisteredSource,
    credential: SourceCredential | None,
    oauth_token: OAuthToken | UserOAuthToken | None = None,
    extra_credentials: dict[str, SourceCredential] | None = None,
    project_id: str | None = None,
    allocated_project_ids: list[str] | None = None,
) -> SourceRecord:
    oauth_active = oauth_token is not None and oauth_token.status == "active"
    requires_auth = source.auth_type == "oauth2"
    mcp_config = _record_mcp_config(source.mcp_config or {}, extra_credentials or {})
    allocations = sorted(set(allocated_project_ids or []))
    allocated_to_project = bool(project_id and project_id in allocations)
    server_setup_required = requires_auth and not source.enabled and source.health_status == "pending_authorization"
    state, guidance = _integration_state(
        source=source,
        requires_auth=requires_auth,
        oauth_token=oauth_token,
        oauth_active=oauth_active,
        project_id=project_id,
        allocated_to_project=allocated_to_project,
        allocation_count=len(allocations),
        server_setup_required=server_setup_required,
    )
    runtime_enabled = source.enabled
    if requires_auth:
        runtime_enabled = oauth_active and (project_id is None or allocated_to_project)
    return SourceRecord(
        id=str(source.id),
        name=source.name,
        project_id=source.project_id,
        kind=source.kind,
        transport=source.transport,
        endpoint_url=source.endpoint_url,
        auth_type=source.auth_type,
        credential_ref=source.credential_ref,
        credential=_record_credential(credential, oauth_token),
        credential_mask=credential.masked_value if credential else ("oauth-connected" if oauth_active else None),
        mcp_config=mcp_config,
        oauth_provider_id=oauth_token.provider_id if oauth_token else None,
        oauth_status=oauth_token.status if oauth_token else None,
        oauth_account_label=oauth_token.account_label if oauth_token else None,
        requires_auth=requires_auth,
        connected=oauth_active,
        connectable=requires_auth,
        domain_hints=list(source.domain_hints or []),
        priority_hint=source.priority_hint,
        enabled=runtime_enabled,
        health_status=source.health_status,
        protected=source.protected,
        created_by=source.created_by,
        allocated_project_ids=allocations,
        allocation_count=len(allocations),
        allocated_to_project=allocated_to_project,
        integration_state=state,
        guidance=guidance,
        category=_source_category(source),
    )


async def list_project_allocations(
    source_id_or_name: str,
    *,
    user_id: str,
) -> dict:
    """List projects allocated to the current user's connected source credential."""
    await ensure_builtin_sources()
    async with async_session_factory() as session:
        source = await _load_source_model(session, source_id_or_name)
        if source is None:
            raise ValueError("Source not found")
        token = await _load_user_source_token(session, source.id, user_id)
        if token is None:
            return {
                "source_id": str(source.id),
                "connected": False,
                "project_ids": [],
                "allocation_count": 0,
                "state": "not_connected",
                "guidance": "Connect this integration before assigning it to projects.",
            }
        project_ids = await _allocation_ids(session, token)
        return {
            "source_id": str(source.id),
            "connected": token.status == "active",
            "project_ids": project_ids,
            "allocation_count": len(project_ids),
            "state": "connected" if project_ids else "connected_unallocated",
            "guidance": None if project_ids else "Connected but not enabled for any project yet.",
        }


async def replace_project_allocations(
    source_id_or_name: str,
    *,
    user_id: str,
    project_ids: list[str],
) -> dict:
    """Replace all project links for the current user's connected source credential."""
    await ensure_builtin_sources()
    normalized = sorted({str(project_id).strip() for project_id in project_ids if str(project_id).strip()})
    async with async_session_factory() as session:
        source = await _load_source_model(session, source_id_or_name)
        if source is None:
            raise ValueError("Source not found")
        token = await _load_user_source_token(session, source.id, user_id)
        if token is None:
            raise ValueError("Connect this integration before assigning it to projects")
        await session.execute(
            delete(SourceProjectLink).where(SourceProjectLink.user_oauth_token_id == token.id)
        )
        for project_id in normalized:
            session.add(SourceProjectLink(user_oauth_token_id=token.id, project_id=project_id))
        await session.commit()
        return {
            "source_id": str(source.id),
            "connected": token.status == "active",
            "project_ids": normalized,
            "allocation_count": len(normalized),
            "state": "connected" if normalized else "connected_unallocated",
            "guidance": None if normalized else "Connected but not enabled for any project yet.",
        }


def _record_mcp_config(
    mcp_config: dict,
    extra_credentials: dict[str, SourceCredential],
) -> dict:
    config = dict(mcp_config or {})
    env_ref = config.get("stdio_env_ref")
    if env_ref and env_ref in extra_credentials:
        try:
            config["stdio_env"] = json.loads(_decrypt(extra_credentials[env_ref].encrypted_value))
        except Exception:
            config["stdio_env"] = {}
    return config


def _record_credential(
    credential: SourceCredential | None,
    oauth_token: OAuthToken | UserOAuthToken | None,
) -> str | None:
    if oauth_token is not None and oauth_token.status == "active":
        return _decrypt(oauth_token.access_token)
    if credential is not None:
        return _decrypt(credential.encrypted_value)
    return None
