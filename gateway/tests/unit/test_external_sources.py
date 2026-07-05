"""Unit tests for external sources (GitHub, Jira, Slack)."""

from gateway.core.sources.github import GitHubSource
from gateway.core.sources.jira import JiraSource
from gateway.core.sources.slack import SlackSource


def test_github_source_initialization_disabled():
    """Test GitHub source initialization with disabled state."""
    source = GitHubSource(enabled=False)
    assert source.is_available() is False


def test_github_source_initialization_enabled():
    """Test GitHub source initialization with enabled state."""
    source = GitHubSource(enabled=True)
    assert source.is_available() is True


def test_jira_source_initialization():
    """Test Jira source initialization."""
    source = JiraSource(enabled=True)
    assert source.is_available() is True


def test_slack_source_initialization():
    """Test Slack source initialization."""
    source = SlackSource(enabled=True)
    assert source.is_available() is True
