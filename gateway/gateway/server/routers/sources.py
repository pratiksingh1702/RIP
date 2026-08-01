"""Sources and editable Gateway settings API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request


from gateway.core import oauth as oauth_manager
from gateway.core.permissions.models import UserRole
from gateway.core.sources.dynamic_mcp import DynamicMCPSource
from gateway.core.sources.registry import get_source_registry
from gateway.server.request_context import gateway_user_id
from gateway.server.schemas.requests import (
    GatewaySettingsRequest,
    OAuthReauthorizeRequest,
    SourceCreateRequest,
    SourceCredentialRequest,
    SourceProjectAllocationRequest,
    SourceUpdateRequest,
)
from gateway.server.schemas.responses import SourceListResponse
from gateway.storage import source_registry as source_store
from gateway.storage.audit_store import get_audit_store
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
async def list_sources(request: Request, project_id: str | None = Query(None)):
    """List all available sources."""
    try:
        user_id = gateway_user_id(request)
        await registry.refresh(project_id=project_id, user_id=user_id)
        sources = await source_store.list_sources(project_id=project_id, user_id=user_id)
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
            project_id=request.project_id,
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
        await registry.refresh(project_id=request.project_id)
        return _source_payload(record)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/presets")
async def source_presets():
    """Return mobile convenience presets."""
    return {"presets": PRESET_CATALOG}


@router.get("/marketplace/servers")
@router.get("/marketplace")
async def get_marketplace_catalog(
    category: str | None = Query(None),
    trust_tier: str | None = Query(None),
    search: str | None = Query(None),
    include_unverified: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
):
    """Return Official MCP Marketplace catalog entries with auto-sync, pagination, and query filtering."""
    from gateway.core.marketplace.catalog_service import catalog_service
    res = catalog_service.list_servers(
        category=category,
        trust_tier=trust_tier,
        search=search,
        include_unverified=include_unverified,
        page=page,
        limit=limit,
    )
    if not res["servers"]:
        await catalog_service.sync()
        res = catalog_service.list_servers(
            category=category,
            trust_tier=trust_tier,
            search=search,
            include_unverified=include_unverified,
            page=page,
            limit=limit,
        )
    return {
        "servers": res["servers"],
        "sources": res["servers"],
        "count": len(res["servers"]),
        "total": res["total"],
        "page": res["page"],
        "limit": res["limit"],
        "has_more": res["has_more"],
    }




@router.post("/marketplace/validate")
async def validate_marketplace_server_json(payload: dict = Body(...)):

    """Validate server.json payload against Official MCP Registry schema validator."""
    from gateway.core.marketplace.catalog_service import catalog_service
    return await catalog_service.validate_server_json(payload)


@router.get("/marketplace/servers/{source_id:path}/versions/{version}")
async def get_marketplace_server_version_detail(source_id: str, version: str):
    """Fetch detailed spec for a specific version from Official Registry."""
    from gateway.core.marketplace.catalog_service import catalog_service
    if source_id.startswith("servers/"):
        source_id = source_id[8:]
    detail = await catalog_service.get_server_version_detail(source_id, version)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Version '{version}' for '{source_id}' not found")
    return detail


@router.get("/marketplace/servers/{source_id:path}/versions")
async def get_marketplace_server_versions(source_id: str):
    """Fetch all available versions for a specific MCP server from Official Registry."""
    from gateway.core.marketplace.catalog_service import catalog_service
    if source_id.startswith("servers/"):
        source_id = source_id[8:]
    if source_id.endswith("/versions"):
        source_id = source_id[:-9]
    return await catalog_service.get_server_versions(source_id)


@router.get("/marketplace/servers/{source_id:path}")
@router.get("/marketplace/{source_id:path}")
async def get_marketplace_detail(source_id: str):
    """Return detailed MCP spec sheet (author, requirements, capabilities, repo URL)."""
    from gateway.core.marketplace.catalog_service import catalog_service
    if source_id.startswith("servers/"):
        source_id = source_id[8:]
    detail = catalog_service.get_server_detail(source_id)
    if detail is None:
        from gateway.core.sources.marketplace import marketplace_engine
        detail = marketplace_engine.get_detail(source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Marketplace item '{source_id}' not found")
    return detail


@router.post("/marketplace/servers/{source_id:path}/connect")
@router.post("/marketplace/{source_id:path}/install")
async def connect_marketplace_source(source_id: str, request: Request, project_id: str | None = Query(None)):
    """Connect/install marketplace server with version pinning into SourceStore."""
    from gateway.core.marketplace.catalog_service import catalog_service
    if source_id.startswith("servers/"):
        source_id = source_id[8:]
    if source_id.endswith("/connect") or source_id.endswith("/install"):
        source_id = source_id.rsplit("/", 1)[0]

    try:
        res = await catalog_service.connect_server(source_id, project_id=project_id)
        record = res["source"]
        return {
            "source": record,
            "status": "connected",
            "requires_auth": res.get("requires_auth", False),
            "auth_scheme": res.get("auth_scheme", "none"),
            "pinned_version": res.get("pinned_version"),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))






@router.get("/settings")
async def get_settings():
    """Return editable Gateway settings."""
    return await source_store.get_gateway_settings()


@router.patch("/settings")
async def patch_settings(request: GatewaySettingsRequest):
    """Patch editable Gateway settings."""
    return await source_store.update_gateway_settings(request.model_dump(exclude_none=True))


@router.get("/{source_id}")
async def get_source(source_id: str, request: Request, project_id: str | None = Query(None)):
    """Get source detail."""
    record = await source_store.get_source(source_id, project_id=project_id, user_id=gateway_user_id(request))
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
    await registry.refresh(project_id=record.project_id)
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
async def replace_credential(source_id: str, payload: SourceCredentialRequest, request: Request):
    """Replace a source credential without revealing the saved value."""
    current = await source_store.get_source(source_id, user_id=gateway_user_id(request))
    if current is not None and current.auth_type == "oauth2":
        try:
            await oauth_manager.ensure_oauth_providers()
            record = await source_store.replace_user_oauth_credential(
                source_id,
                user_id=gateway_user_id(request),
                credential=payload.credential,
                provider_id=current.oauth_provider_id or current.name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        record = await source_store.replace_credential(source_id, payload.credential)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")
    await registry.refresh(project_id=record.project_id)
    await _audit_source_event(
        action="source_credential_update",
        source=record.name,
        user_id=gateway_user_id(request),
        reason="credential replaced from mobile/API",
    )
    return _source_payload(record, detail=True)


@router.post("/{source_id}/test")
async def test_source(source_id: str, request: Request, project_id: str | None = Query(None)):
    """Test source connection using the mobile four-state contract."""
    user_id = gateway_user_id(request)
    record = await source_store.get_source(source_id, project_id=project_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if record.name in {"rip", "github", "jira", "slack"}:
        await registry.refresh(project_id=record.project_id or project_id, user_id=user_id)
        source = registry.get_source(record.name)
        ok = await source.health_check() if source else False
        return {"status": "ok" if ok else "unreachable", "source": record.name}
    dynamic = DynamicMCPSource(record)
    return await dynamic.test_connection_detailed()



@router.post("/{source_id}/oauth/reauthorize")
async def reauthorize_oauth_source(source_id: str, request: OAuthReauthorizeRequest, http_request: Request):
    """Restart OAuth authorization for an existing source."""
    try:
        result = await oauth_manager.reauthorize_source(
            source_id,
            redirect_uri=request.redirect_uri,
            client_type=request.client_type,
            requested_by=request.requested_by,
            user_id=gateway_user_id(http_request),
            project_id=request.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await registry.refresh(project_id=request.project_id, user_id=gateway_user_id(http_request))
    return result


@router.post("/{source_id}/oauth/revoke")
async def revoke_oauth_source(source_id: str, request: Request, project_id: str | None = Query(None)):
    """Disconnect an OAuth source without deleting the source row."""
    try:
        result = await oauth_manager.revoke_source(
            source_id,
            user_id=gateway_user_id(request),
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await registry.refresh(project_id=project_id, user_id=gateway_user_id(request))
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
    await registry.refresh(project_id=record.project_id)
    return {"status": "ok", "source": source_name, "enabled": record.enabled}


def _source_payload(source: SourceRecord, *, detail: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": source.id,
        "name": source.name,
        "project_id": source.project_id,
        "scope": "global" if source.project_id is None else "project",
        "kind": source.kind,
        "transport": source.transport,
        "endpoint_url": source.endpoint_url,
        "mcp_config": _public_mcp_config(source.mcp_config),
        "tool_name": (source.mcp_config or {}).get("tool_name", "search"),
        "capabilities": (source.mcp_config or {}).get("capabilities"),
        "auth_type": source.auth_type,
        "credential_mask": source.credential_mask,
        "oauth_provider_id": source.oauth_provider_id or (source.name if source.requires_auth else None),
        "oauth_status": source.oauth_status or _oauth_status_from_health(source.health_status),
        "oauth_account_label": source.oauth_account_label,
        "requires_auth": source.requires_auth,
        "connected": source.connected,
        "connectable": source.connectable,
        "integration_state": source.integration_state,
        "guidance": source.guidance,
        "category": source.category,
        "allocated_project_ids": source.allocated_project_ids or [],
        "allocation_count": source.allocation_count,
        "allocated_to_project": source.allocated_to_project,
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


@router.get("/{source_id}/projects")
async def get_source_projects(source_id: str, request: Request):
    """Return the current user's project allocations for this connected integration."""
    try:
        return await source_store.list_project_allocations(
            source_id,
            user_id=gateway_user_id(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{source_id}/projects")
async def put_source_projects(source_id: str, payload: SourceProjectAllocationRequest, request: Request):
    """Replace all project allocations for this connected integration."""
    try:
        result = await source_store.replace_project_allocations(
            source_id,
            user_id=gateway_user_id(request),
            project_ids=payload.project_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await registry.refresh(user_id=gateway_user_id(request))
    await _audit_source_event(
        action="source_project_allocation_update",
        source=source_id,
        user_id=gateway_user_id(request),
        reason=f"{len(result['project_ids'])} project(s) allocated",
    )
    return result


async def _audit_source_event(action: str, source: str, user_id: str | None, reason: str) -> None:
    await get_audit_store().log_access(
        session_id="integrations",
        role=UserRole.DEVELOPER,
        action=action,
        allowed=True,
        user_id=user_id,
        source=source,
        reason=reason,
    )


def _visible_in_mobile_sources(source: SourceRecord) -> bool:
    if source.name == "rip":
        return True
    return True


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
