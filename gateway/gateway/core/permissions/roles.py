"""Role definitions and policies."""

from .models import AccessPolicy, UserRole

DEFAULT_POLICIES = {
    UserRole.JUNIOR_DEV: AccessPolicy(
        role=UserRole.JUNIOR_DEV,
        allowed_sources=["rip"],
        max_token_budget=8000,
        can_access_sensitive_domains=False,
        can_use_sandbox=False,
        can_connect_machine=False,
        can_share_sandbox=False,
    ),
    UserRole.DEVELOPER: AccessPolicy(
        role=UserRole.DEVELOPER,
        allowed_sources=["rip", "*"],
        max_token_budget=12000,
        can_access_sensitive_domains=True,
        can_use_sandbox=True,
        can_connect_machine=True,
        can_share_sandbox=True,
    ),
    UserRole.SENIOR_DEV: AccessPolicy(
        role=UserRole.SENIOR_DEV,
        allowed_sources=["rip", "*"],
        max_token_budget=20000,
        can_access_sensitive_domains=True,
        can_use_sandbox=True,
        can_connect_machine=True,
        can_share_sandbox=True,
    ),
    UserRole.CI_AGENT: AccessPolicy(
        role=UserRole.CI_AGENT,
        allowed_sources=["rip"],
        max_token_budget=6000,
        can_access_sensitive_domains=False,
        can_use_sandbox=True,
        can_connect_machine=False,
        can_share_sandbox=False,
    ),
}

SENSITIVE_DOMAINS = ["payment", "auth", "security"]
