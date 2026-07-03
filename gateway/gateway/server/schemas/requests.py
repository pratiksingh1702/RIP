"""HTTP request schemas."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class GetContextRequest(BaseModel):
    """Request to get context for a task."""
    task: str
    max_tokens: int = 12000
    role: str = "developer"
    session_id: Optional[str] = None


class ValidateChangeRequest(BaseModel):
    """Request to validate a code change."""
    diff: str
    files: Optional[list[str]] = None


class FeedbackRequest(BaseModel):
    """Feedback on a gateway response."""
    session_id: str
    rating: Optional[int] = None
    was_helpful: Optional[bool] = None
    missing_context: list[str] = []
    irrelevant_context: list[str] = []
    comment: Optional[str] = None


class SourceCreateRequest(BaseModel):
    """Register a built-in preset or custom MCP source."""
    name: str
    kind: str = "mcp"
    transport: str = "http"
    endpoint_url: Optional[str] = None
    stdio_command: Optional[str] = None
    stdio_args: list[str] = Field(default_factory=list)
    stdio_cwd: Optional[str] = None
    stdio_env: dict[str, str] = Field(default_factory=dict)
    auth_type: str = "none"
    credential: Optional[str] = None
    tool_name: str = "search"
    tool_arguments_template: Optional[dict[str, Any]] = None
    domain_hints: list[str] = []
    priority_hint: int = 50
    enabled: bool = True


class SourceUpdateRequest(BaseModel):
    """Patch source metadata editable from mobile Settings."""
    name: Optional[str] = None
    transport: Optional[str] = None
    endpoint_url: Optional[str] = None
    stdio_command: Optional[str] = None
    stdio_args: Optional[list[str]] = None
    stdio_cwd: Optional[str] = None
    stdio_env: Optional[dict[str, str]] = None
    auth_type: Optional[str] = None
    tool_name: Optional[str] = None
    tool_arguments_template: Optional[dict[str, Any]] = None
    domain_hints: Optional[list[str]] = None
    priority_hint: Optional[int] = None
    enabled: Optional[bool] = None


class SourceCredentialRequest(BaseModel):
    """Write-only credential replacement."""
    credential: str


class GatewaySettingsRequest(BaseModel):
    """Editable Gateway defaults."""
    default_max_tokens: Optional[int] = None
    overhead_reserve_ratio: Optional[float] = None
    min_tokens_per_source: Optional[int] = None
    default_role: Optional[str] = None


class OAuthInitiateRequest(BaseModel):
    """Start an OAuth authorization flow."""
    provider_id: str
    source_name: Optional[str] = None
    domain_hints: list[str] = []
    redirect_uri: str
    client_type: str = "mobile"
    requested_by: Optional[str] = None


class OAuthCallbackRequest(BaseModel):
    """Complete an OAuth authorization flow."""
    state: str
    code: str
    requested_by: Optional[str] = None


class OAuthReauthorizeRequest(BaseModel):
    """Restart authorization for an existing OAuth source."""
    redirect_uri: str
    client_type: str = "mobile"
    requested_by: Optional[str] = None
