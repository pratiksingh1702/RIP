"""Universal MCP Auth Challenge Resolver for parsing WWW-Authenticate, OAuth 2.0, API keys, Basic Auth, and Env Vars."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AuthType(str, Enum):
    OAUTH2 = "oauth2"
    WWW_AUTHENTICATE = "www_authenticate"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    ENV_VARS = "env_vars"
    CUSTOM_HEADER = "custom_header"


@dataclass
class AuthChallenge:
    auth_type: AuthType
    source_id: str
    source_name: str
    instructions: str
    authorization_url: Optional[str] = None
    token_url: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    header_name: str = "Authorization"
    required_env_vars: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auth_type": self.auth_type.value,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "instructions": self.instructions,
            "authorization_url": self.authorization_url,
            "token_url": self.token_url,
            "scopes": self.scopes,
            "header_name": self.header_name,
            "required_env_vars": self.required_env_vars,
            "metadata": self.metadata,
        }


class AuthResolver:
    """Parses auth challenges from HTTP 401 headers, JSON-RPC errors, or tool definitions."""

    @classmethod
    def resolve_challenge(
        cls,
        source_id: str,
        source_name: str,
        status_code: int,
        headers: Dict[str, str],
        body: Optional[Dict[str, Any]] = None,
    ) -> AuthChallenge:
        headers_lower = {k.lower(): v for k, v in headers.items()}
        www_auth = headers_lower.get("www-authenticate")

        # 1. Parse WWW-Authenticate Header
        if www_auth:
            return cls._parse_www_authenticate(source_id, source_name, www_auth)

        # 2. Parse MCP JSON-RPC Auth Error (Spec 2024-11-05 format)
        if isinstance(body, dict) and "error" in body:
            err_data = body["error"].get("data", {})
            auth_type_str = err_data.get("auth_type", "").lower()
            
            if auth_type_str == "oauth" or "authorization_url" in err_data:
                return AuthChallenge(
                    auth_type=AuthType.OAUTH2,
                    source_id=source_id,
                    source_name=source_name,
                    instructions=err_data.get("instructions", f"OAuth authentication required for {source_name}."),
                    authorization_url=err_data.get("authorization_url"),
                    token_url=err_data.get("token_url"),
                    scopes=err_data.get("scopes", []),
                    metadata=err_data,
                )
            elif auth_type_str == "api_key":
                return AuthChallenge(
                    auth_type=AuthType.API_KEY,
                    source_id=source_id,
                    source_name=source_name,
                    instructions=err_data.get("instructions", f"API Key required for {source_name}."),
                    header_name=err_data.get("header_name", "Authorization"),
                    metadata=err_data,
                )
            elif auth_type_str == "env_vars":
                return AuthChallenge(
                    auth_type=AuthType.ENV_VARS,
                    source_id=source_id,
                    source_name=source_name,
                    instructions=err_data.get("instructions", f"Environment variables required for {source_name}."),
                    required_env_vars=err_data.get("required_env_vars", []),
                    metadata=err_data,
                )

        # 3. Default Fallback Challenge
        return AuthChallenge(
            auth_type=AuthType.API_KEY,
            source_id=source_id,
            source_name=source_name,
            instructions=f"Authentication required for {source_name}. Please enter your token or API Key.",
            header_name="Authorization",
        )

    @classmethod
    def _parse_www_authenticate(cls, source_id: str, source_name: str, header_val: str) -> AuthChallenge:
        # Bearer scheme check
        if header_val.lower().startswith("bearer"):
            auth_uri_match = re.search(r'auth_uri="([^"]+)"', header_val, re.IGNORECASE)
            realm_match = re.search(r'realm="([^"]+)"', header_val, re.IGNORECASE)

            if auth_uri_match:
                return AuthChallenge(
                    auth_type=AuthType.OAUTH2,
                    source_id=source_id,
                    source_name=source_name,
                    instructions=f"OAuth login required for {realm_match.group(1) if realm_match else source_name}.",
                    authorization_url=auth_uri_match.group(1),
                )
            return AuthChallenge(
                auth_type=AuthType.BEARER_TOKEN,
                source_id=source_id,
                source_name=source_name,
                instructions=f"Bearer Token required for {realm_match.group(1) if realm_match else source_name}.",
                header_name="Authorization",
            )

        # Basic auth check
        if header_val.lower().startswith("basic"):
            realm_match = re.search(r'realm="([^"]+)"', header_val, re.IGNORECASE)
            return AuthChallenge(
                auth_type=AuthType.BASIC_AUTH,
                source_id=source_id,
                source_name=source_name,
                instructions=f"Basic Auth (Username & Password / Key & Secret) required for {realm_match.group(1) if realm_match else source_name}.",
                header_name="Authorization",
            )

        # Fallback for custom WWW-Authenticate headers
        return AuthChallenge(
            auth_type=AuthType.API_KEY,
            source_id=source_id,
            source_name=source_name,
            instructions=f"Authentication challenge received: {header_val}",
            header_name="Authorization",
        )
