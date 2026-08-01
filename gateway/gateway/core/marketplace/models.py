"""Marketplace data models for Official MCP Registry catalog integration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HeaderRequirement(BaseModel):
    name: str
    description: str = ""
    is_required: bool = False
    is_secret: bool = False
    default: Optional[str] = None


class EnvVarRequirement(BaseModel):
    name: str
    description: str = ""
    is_required: bool = False
    is_secret: bool = False
    default: Optional[str] = None


class MarketplaceEntry(BaseModel):
    id: str  # Canonical reverse-DNS identifier (e.g. io.github.user/slack)
    display_name: str
    description: str
    category: str = "uncategorized"  # productivity / dev-tools / data / communication / uncategorized
    auth_scheme: str = "none"  # oauth2_pkce | api_key | bearer_token | basic_auth | env_vars | none
    install_type: str = "remote_http"  # remote_http | remote_sse | stdio_npx | stdio_uvx
    repo_url: str = ""
    website_url: str = ""
    version: str = "latest"
    tool_count: Optional[int] = None
    trust_tier: str = "community"  # verified | community | unverified
    last_synced_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    headers_required: List[HeaderRequirement] = Field(default_factory=list)
    env_vars_required: List[EnvVarRequirement] = Field(default_factory=list)
    remotes: List[Dict[str, Any]] = Field(default_factory=list)
    packages: List[Dict[str, Any]] = Field(default_factory=list)
    repository: Dict[str, Any] = Field(default_factory=dict)
    is_official: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
