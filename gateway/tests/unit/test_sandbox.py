"""Tests for Project Sandbox."""
from __future__ import annotations
import pytest
from gateway.core.sandbox.security import SecurityPolicy, CommandRisk

class TestSecurityPolicy:
    def setup_method(self):
        self.policy = SecurityPolicy()

    def test_safe_commands(self):
        allowed, reason, risk = self.policy.validate_command("ls -la")
        assert allowed is True
        assert risk == CommandRisk.SAFE

    def test_restricted_commands(self):
        allowed, reason, risk = self.policy.validate_command("rm file.txt")
        assert allowed is True
        assert risk == CommandRisk.RESTRICTED

    def test_blocked_commands(self):
        allowed, reason, risk = self.policy.validate_command("rm -rf /")
        assert allowed is False
        assert risk == CommandRisk.BLOCKED

    def test_blocked_shutdown(self):
        allowed, reason, risk = self.policy.validate_command("shutdown now")
        assert allowed is False

    def test_sanitize_password(self):
        sanitized = self.policy.sanitize_for_logging("login --password secret123")
        assert "secret123" not in sanitized
        assert "***" in sanitized

    def test_sanitize_token(self):
        sanitized = self.policy.sanitize_for_logging("export TOKEN=abc123xyz")
        assert "abc123xyz" not in sanitized

    def test_python_command_allowed(self):
        allowed, _, risk = self.policy.validate_command("python script.py")
        assert allowed is True

    def test_git_status_allowed(self):
        allowed, _, risk = self.policy.validate_command("git status")
        assert allowed is True

    def test_git_push_restricted(self):
        allowed, reason, risk = self.policy.validate_command("git push origin main")
        assert allowed is True
        assert risk == CommandRisk.RESTRICTED

    def test_curl_allowed(self):
        allowed, _, risk = self.policy.validate_command("curl https://example.com")
        assert allowed is True

    def test_empty_command_blocked(self):
        allowed, _, _ = self.policy.validate_command("")
        assert allowed is False

    def test_needs_approval_for_restricted(self):
        assert self.policy.needs_approval(CommandRisk.RESTRICTED) is True

    def test_needs_approval_for_blocked(self):
        assert self.policy.needs_approval(CommandRisk.BLOCKED) is True

    def test_no_approval_for_safe(self):
        assert self.policy.needs_approval(CommandRisk.SAFE) is False
