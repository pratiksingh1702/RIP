"""HTTP request schemas."""

from typing import Any

from pydantic import BaseModel, Field


class GetContextRequest(BaseModel):
    """Request to get context for a task."""
    task: str
    max_tokens: int = 12000
    role: str = "developer"
    session_id: str | None = None
    project_id: str | None = None


class ValidateChangeRequest(BaseModel):
    """Request to validate a code change."""
    diff: str
    files: list[str] | None = None


class FeedbackRequest(BaseModel):
    """Feedback on a gateway response."""
    session_id: str
    rating: int | None = None
    was_helpful: bool | None = None
    missing_context: list[str] = []
    irrelevant_context: list[str] = []
    comment: str | None = None
    prompt_id: str | None = None


class SourceCreateRequest(BaseModel):
    """Register a built-in preset or custom MCP source."""
    name: str
    project_id: str | None = None
    kind: str = "mcp"
    transport: str = "http"
    endpoint_url: str | None = None
    stdio_command: str | None = None
    stdio_args: list[str] = Field(default_factory=list)
    stdio_cwd: str | None = None
    stdio_env: dict[str, str] = Field(default_factory=dict)
    auth_type: str = "none"
    credential: str | None = None
    tool_name: str = "search"
    tool_arguments_template: dict[str, Any] | None = None
    domain_hints: list[str] = []
    priority_hint: int = 50
    enabled: bool = True


class SourceUpdateRequest(BaseModel):
    """Patch source metadata editable from mobile Settings."""
    name: str | None = None
    project_id: str | None = None
    transport: str | None = None
    endpoint_url: str | None = None
    stdio_command: str | None = None
    stdio_args: list[str] | None = None
    stdio_cwd: str | None = None
    stdio_env: dict[str, str] | None = None
    auth_type: str | None = None
    tool_name: str | None = None
    tool_arguments_template: dict[str, Any] | None = None
    domain_hints: list[str] | None = None
    priority_hint: int | None = None
    enabled: bool | None = None


class SourceCredentialRequest(BaseModel):
    """Write-only credential replacement."""
    credential: str


class GatewaySettingsRequest(BaseModel):
    """Editable Gateway defaults."""
    default_max_tokens: int | None = None
    overhead_reserve_ratio: float | None = None
    min_tokens_per_source: int | None = None
    default_role: str | None = None


class OAuthInitiateRequest(BaseModel):
    """Start an OAuth authorization flow."""
    provider_id: str
    source_name: str | None = None
    project_id: str | None = None
    domain_hints: list[str] = []
    redirect_uri: str
    client_type: str = "mobile"
    requested_by: str | None = None


class OAuthCallbackRequest(BaseModel):
    """Complete an OAuth authorization flow."""
    state: str
    code: str
    requested_by: str | None = None


class OAuthReauthorizeRequest(BaseModel):
    """Restart authorization for an existing OAuth source."""
    redirect_uri: str
    project_id: str | None = None
    client_type: str = "mobile"
    requested_by: str | None = None


class SourceProjectAllocationRequest(BaseModel):
    """Replace project allocations for a connected integration."""
    project_ids: list[str] = Field(default_factory=list)
