"""Helpers for deriving Gateway caller scope from RIP requests."""

from __future__ import annotations

from fastapi import Request


def gateway_user_id(request: Request | None) -> str | None:
    """Return a stable per-API-key user id for Gateway-owned credentials."""
    if request is None:
        return None
    api_key = getattr(request.state, "api_key", None)
    if api_key is None:
        return None
    key_id = getattr(api_key, "id", None)
    if key_id is not None:
        return f"api-key:{key_id}"
    prefix = getattr(api_key, "prefix", None)
    if prefix:
        return f"api-key-prefix:{prefix}"
    name = getattr(api_key, "name", None)
    return f"api-key-name:{name}" if name else None
