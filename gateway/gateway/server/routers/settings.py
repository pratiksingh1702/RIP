"""Editable Gateway defaults router."""

from fastapi import APIRouter

from gateway.server.schemas.requests import GatewaySettingsRequest
from gateway.storage import source_registry as source_store

router = APIRouter()


@router.get("")
@router.get("/")
async def get_gateway_settings():
    """Return editable Gateway settings."""
    return await source_store.get_gateway_settings()


@router.patch("")
@router.patch("/")
async def patch_gateway_settings(request: GatewaySettingsRequest):
    """Patch editable Gateway settings."""
    return await source_store.update_gateway_settings(request.model_dump(exclude_none=True))
