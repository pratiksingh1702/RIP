"""Persistent source registry and Gateway settings helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from itertools import cycle
from uuid import UUID, uuid4

from sqlalchemy import select

from gateway.config import settings
from gateway.storage.database import async_session_factory
from gateway.storage.models import GatewaySetting, OAuthToken, RegisteredSource, SourceCredential


@dataclass(slots=True)
class SourceRecord:
    """Serializable registry record used by runtime code."""

    id: str
    name: str
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
        "auth_type": "bearer" if settings.github_token else "none",
        "mcp_config": {"tool_name": "search"},
        "enabled": settings.github_mcp_enabled,
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
        "auth_type": "bearer" if settings.jira_token else "none",
        "mcp_config": {"tool_name": "search"},
        "enabled": settings.jira_mcp_enabled,
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
        "auth_type": "bearer" if settings.slack_token else "none",
        "mcp_config": {"tool_name": "search"},
        "enabled": settings.slack_mcp_enabled,
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
            source.mcp_config = source.mcp_config or dict(defaults.get("mcp_config") or {})
            if source.name == "rip":
                source.enabled = True
                source.health_status = "ok"
            changed = True
        if changed:
            await session.commit()


async def list_sources() -> list[SourceRecord]:
    """Return all registered source rows with decrypted credentials for runtime use."""
    await ensure_builtin_sources()
    async with async_session_factory() as session:
        sources = (await session.execute(select(RegisteredSource).order_by(RegisteredSource.priority_hint.desc()))).scalars().all()
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
        token_rows = (
            await session.execute(
                select(OAuthToken).where(OAuthToken.source_id.in_([source.id for source in sources]))
            )
        ).scalars()
        oauth_tokens = {token.source_id: token for token in token_rows}
        return [
            _record_from_model(
                source,
                credentials.get(source.credential_ref or ""),
                oauth_tokens.get(source.id),
                credentials,
            )
            for source in sources
        ]


async def get_source(source_id_or_name: str) -> SourceRecord | None:
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
        oauth_token = await session.get(OAuthToken, source.id)
        extra_credentials = {}
        env_ref = (source.mcp_config or {}).get("stdio_env_ref")
        if env_ref:
            env_credential = await session.get(SourceCredential, env_ref)
            if env_credential:
                extra_credentials[env_ref] = env_credential
        return _record_from_model(source, credential, oauth_token, extra_credentials)


async def create_source(
    *,
    name: str,
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
        source = RegisteredSource(
            name=name.strip(),
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
        for field in ("name", "endpoint_url", "auth_type", "transport"):
            if field in updates and updates[field] is not None:
                setattr(source, field, updates[field])
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
        if source.protected:
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


async def get_gateway_settings() -> dict:
    """Return editable Gateway defaults."""
    async with async_session_factory() as session:
        row = await session.get(GatewaySetting, "defaults")
        stored = row.value if row else {}
    return {
        "default_max_tokens": stored.get("default_max_tokens", settings.default_max_tokens),
        "overhead_reserve_ratio": stored.get("overhead_reserve_ratio", settings.overhead_reserve_ratio),
        "min_tokens_per_source": stored.get("min_tokens_per_source", settings.min_tokens_per_source),
        "default_role": stored.get("default_role", settings.default_role),
    }


async def update_gateway_settings(updates: dict) -> dict:
    """Persist editable Gateway defaults."""
    current = await get_gateway_settings()
    for key in ("default_max_tokens", "overhead_reserve_ratio", "min_tokens_per_source", "default_role"):
        if key in updates and updates[key] is not None:
            current[key] = updates[key]
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


def _record_from_model(
    source: RegisteredSource,
    credential: SourceCredential | None,
    oauth_token: OAuthToken | None = None,
    extra_credentials: dict[str, SourceCredential] | None = None,
) -> SourceRecord:
    oauth_active = oauth_token is not None and oauth_token.status == "active"
    mcp_config = _record_mcp_config(source.mcp_config or {}, extra_credentials or {})
    return SourceRecord(
        id=str(source.id),
        name=source.name,
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
        domain_hints=list(source.domain_hints or []),
        priority_hint=source.priority_hint,
        enabled=source.enabled and (source.auth_type != "oauth2" or oauth_active),
        health_status=source.health_status,
        protected=source.protected,
        created_by=source.created_by,
    )


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
    oauth_token: OAuthToken | None,
) -> str | None:
    if oauth_token is not None and oauth_token.status == "active":
        return _decrypt(oauth_token.access_token)
    if credential is not None:
        return _decrypt(credential.encrypted_value)
    return None
