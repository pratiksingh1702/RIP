"""Sources and editable Gateway settings API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from gateway.core import oauth as oauth_manager
from gateway.core.sources.dynamic_mcp import DynamicMCPSource
from gateway.core.sources.registry import get_source_registry
from gateway.server.schemas.requests import (
    GatewaySettingsRequest,
    OAuthReauthorizeRequest,
    SourceCreateRequest,
    SourceCredentialRequest,
    SourceUpdateRequest,
)
from gateway.server.schemas.responses import SourceListResponse
from gateway.storage import source_registry as source_store
from gateway.storage.source_registry import SourceRecord

router = APIRouter()
registry = get_source_registry()

PRESET_CATALOG = [
    {
        "name": "GitHub",
        "slug": "github",
        "transport": "http",
        "endpoint_pattern": "https://api.github.com",
        "auth_type": "bearer",
        "domain_hints": ["code", "review", "git", "api"],
    },
    {
        "name": "Jira",
        "slug": "jira",
        "transport": "http",
        "endpoint_pattern": "https://your-domain.atlassian.net",
        "auth_type": "bearer",
        "domain_hints": ["planning", "tickets", "requirements"],
    },
    {
        "name": "Slack",
        "slug": "slack",
        "transport": "http",
        "endpoint_pattern": "https://slack.com/api",
        "auth_type": "bearer",
        "domain_hints": ["discussion", "support", "docs"],
    },
    {
        "name": "Linear",
        "slug": "linear",
        "transport": "http",
        "endpoint_pattern": "https://api.linear.app/mcp",
        "auth_type": "bearer",
        "domain_hints": ["planning", "tickets", "product"],
    },
    {
        "name": "Notion",
        "slug": "notion",
        "transport": "http",
        "endpoint_pattern": "https://api.notion.com/mcp",
        "auth_type": "bearer",
        "domain_hints": ["docs", "knowledge", "planning"],
    },
]


@router.get("", response_model=SourceListResponse)
@router.get("/", response_model=SourceListResponse)
async def list_sources():
    """List all available sources."""
    try:
        await registry.refresh()
        sources = await source_store.list_sources()
        return SourceListResponse(
            sources=[
                _source_payload(source)
                for source in sources
                if _visible_in_mobile_sources(source)
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("")
@router.post("/")
async def create_source(request: SourceCreateRequest):
    """Register a new MCP-compatible source."""
    try:
        record = await source_store.create_source(
            name=request.name,
            kind=request.kind,
            transport=_normalize_transport(request.transport),
            endpoint_url=request.endpoint_url,
            auth_type=request.auth_type,
            credential=request.credential,
            mcp_config=_mcp_config_from_request(request),
            domain_hints=request.domain_hints,
            priority_hint=request.priority_hint,
            enabled=request.enabled,
            created_by="mobile",
        )
        await registry.refresh()
        return _source_payload(record)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/presets")
async def source_presets():
    """Return mobile convenience presets."""
    return {"presets": PRESET_CATALOG}


@router.get("/settings")
async def get_settings():
    """Return editable Gateway settings."""
    return await source_store.get_gateway_settings()


@router.patch("/settings")
async def patch_settings(request: GatewaySettingsRequest):
    """Patch editable Gateway settings."""
    return await source_store.update_gateway_settings(request.model_dump(exclude_none=True))


@router.get("/{source_id}")
async def get_source(source_id: str):
    """Get source detail."""
    record = await source_store.get_source(source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_payload(record, detail=True)


@router.patch("/{source_id}")
async def patch_source(source_id: str, request: SourceUpdateRequest):
    """Patch source metadata."""
    try:
        updates = request.model_dump(exclude_none=True)
        mcp_config = _mcp_config_from_request(request, partial=True)
        if mcp_config:
            updates["mcp_config"] = mcp_config
        if "transport" in updates:
            updates["transport"] = _normalize_transport(updates["transport"])
        for key in (
            "stdio_command",
            "stdio_args",
            "stdio_cwd",
            "stdio_env",
            "tool_name",
            "tool_arguments_template",
        ):
            updates.pop(key, None)
        record = await source_store.update_source(source_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")
    registry.set_enabled(record.name, record.enabled)
    await registry.refresh()
    return _source_payload(record, detail=True)


@router.delete("/{source_id}")
async def delete_source(source_id: str):
    """Remove a dynamic source."""
    try:
        deleted = await source_store.delete_source(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    await registry.refresh()
    return {"status": "ok", "source": source_id}


@router.post("/{source_id}/credential")
async def replace_credential(source_id: str, request: SourceCredentialRequest):
    """Replace a source credential without revealing the saved value."""
    record = await source_store.replace_credential(source_id, request.credential)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")
    await registry.refresh()
    return _source_payload(record, detail=True)


@router.post("/{source_id}/test")
async def test_source(source_id: str):
    """Test source connection using the mobile four-state contract."""
    record = await source_store.get_source(source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if record.name in {"rip", "github", "jira", "slack"}:
        await registry.refresh()
        source = registry.get_source(record.name)
        ok = await source.health_check() if source else False
        return {"status": "ok" if ok else "unreachable", "source": record.name}
    dynamic = DynamicMCPSource(record)
    return {"status": await dynamic.test_connection(), "source": record.name}


@router.post("/{source_id}/oauth/reauthorize")
async def reauthorize_oauth_source(source_id: str, request: OAuthReauthorizeRequest):
    """Restart OAuth authorization for an existing source."""
    try:
        result = await oauth_manager.reauthorize_source(
            source_id,
            redirect_uri=request.redirect_uri,
            client_type=request.client_type,
            requested_by=request.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await registry.refresh()
    return result


@router.post("/{source_id}/oauth/revoke")
async def revoke_oauth_source(source_id: str):
    """Disconnect an OAuth source without deleting the source row."""
    try:
        result = await oauth_manager.revoke_source(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await registry.refresh()
    return result


@router.post("/{source_name}/enable")
async def enable_source(source_name: str):
    """Legacy route: enable a source."""
    return await _set_enabled(source_name, True)


@router.post("/{source_name}/disable")
async def disable_source(source_name: str):
    """Legacy route: disable a source."""
    return await _set_enabled(source_name, False)


async def _set_enabled(source_name: str, enabled: bool):
    try:
        record = await source_store.update_source(source_name, {"enabled": enabled})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")
    await registry.refresh()
    return {"status": "ok", "source": source_name, "enabled": record.enabled}


def _source_payload(source: SourceRecord, *, detail: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": source.id,
        "name": source.name,
        "kind": source.kind,
        "transport": source.transport,
        "endpoint_url": source.endpoint_url,
        "mcp_config": _public_mcp_config(source.mcp_config),
        "tool_name": (source.mcp_config or {}).get("tool_name", "search"),
        "capabilities": (source.mcp_config or {}).get("capabilities"),
        "auth_type": source.auth_type,
        "credential_mask": source.credential_mask,
        "oauth_provider_id": source.oauth_provider_id,
        "oauth_status": source.oauth_status or _oauth_status_from_health(source.health_status),
        "oauth_account_label": source.oauth_account_label,
        "domain_hints": source.domain_hints,
        "priority_hint": source.priority_hint,
        "enabled": source.protected or source.enabled,
        "available": source.protected or source.enabled,
        "healthy": source.health_status == "ok",
        "health_status": source.health_status,
        "always_on": source.protected,
        "protected": source.protected,
        "toggleable": not source.protected,
        "created_by": source.created_by,
    }
    if detail:
        payload["credential_ref"] = source.credential_ref
        payload["credential_write_only"] = True
    return payload


def _visible_in_mobile_sources(source: SourceRecord) -> bool:
    if source.name == "rip":
        return True
    return source.kind != "builtin"


def _normalize_transport(transport: str) -> str:
    value = (transport or "streamable_http").lower()
    return "streamable_http" if value == "http" else value


def _mcp_config_from_request(
    request: SourceCreateRequest | SourceUpdateRequest,
    *,
    partial: bool = False,
) -> dict[str, Any]:
    payload = request.model_dump(exclude_none=True)
    config: dict[str, Any] = {}
    for key in ("stdio_command", "stdio_args", "stdio_cwd", "stdio_env", "tool_arguments_template"):
        if key in payload:
            config[key] = payload[key]
    if "tool_name" in payload:
        config["tool_name"] = payload["tool_name"] or "search"
    elif not partial:
        config["tool_name"] = "search"
    return config


def _public_mcp_config(config: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(config or {})
    raw.pop("stdio_env", None)
    raw.pop("stdio_env_ref", None)
    if "stdio_env_mask" in raw:
        raw["stdio_env"] = raw.pop("stdio_env_mask")
    return raw


def _oauth_status_from_health(health_status: str) -> str | None:
    if health_status in {"pending_authorization", "needs_reauth", "revoked"}:
        return health_status
    return None
