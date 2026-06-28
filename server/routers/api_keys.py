"""API Key management endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_keys import create_api_key, list_api_keys, revoke_api_key
from core.storage.database import get_db_session

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., description="Human-readable name for the API key")
    description: str | None = Field(None, description="Optional description of the key's purpose")
    expires_in_days: int | None = Field(None, description="Optional number of days until the key expires")


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    prefix: str
    is_active: bool
    expires_at: str | None
    last_used_at: str | None
    created_at: str
    description: str | None

    @classmethod
    def from_model(cls, api_key):
        return cls(
            id=api_key.id,
            name=api_key.name,
            prefix=api_key.prefix,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
            last_used_at=api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            created_at=api_key.created_at.isoformat(),
            description=api_key.description,
        )


class CreateApiKeyResponse(BaseModel):
    api_key: str
    key_info: ApiKeyResponse


@router.post("", response_model=CreateApiKeyResponse)
async def create_new_api_key(
    request: CreateApiKeyRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Create a new API key."""
    plaintext_key, api_key = await create_api_key(
        db,
        name=request.name,
        description=request.description,
        expires_in_days=request.expires_in_days,
    )
    return CreateApiKeyResponse(
        api_key=plaintext_key,
        key_info=ApiKeyResponse.from_model(api_key),
    )


@router.get("", response_model=list[ApiKeyResponse])
async def get_all_api_keys(
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """List all API keys."""
    api_keys = await list_api_keys(db)
    return [ApiKeyResponse.from_model(key) for key in api_keys]


@router.delete("/{api_key_id}")
async def revoke_existing_api_key(
    api_key_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Revoke an API key."""
    success = await revoke_api_key(db, api_key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key revoked successfully"}
