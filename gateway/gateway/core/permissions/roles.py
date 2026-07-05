"""Role definitions and policies."""

from .models import AccessPolicy, UserRole

# Default access policies
DEFAULT_POLICIES = {
    UserRole.JUNIOR_DEV: AccessPolicy(
        role=UserRole.JUNIOR_DEV,
        allowed_sources=["rip"],
        max_token_budget=8000,
        can_access_sensitive_domains=False
    ),
    UserRole.DEVELOPER: AccessPolicy(
        role=UserRole.DEVELOPER,
        allowed_sources=["rip", "*"],
        max_token_budget=12000,
        can_access_sensitive_domains=True
    ),
    UserRole.SENIOR_DEV: AccessPolicy(
        role=UserRole.SENIOR_DEV,
        allowed_sources=["rip", "*"],
        max_token_budget=20000,
        can_access_sensitive_domains=True
    ),
    UserRole.CI_AGENT: AccessPolicy(
        role=UserRole.CI_AGENT,
        allowed_sources=["rip"],
        max_token_budget=6000,
        can_access_sensitive_domains=False
    )
}


# Sensitive domains that are restricted for junior devs
SENSITIVE_DOMAINS = ["payment", "auth", "security"]
