"""Unit tests for storage (Phase 1 smoke tests)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.storage.database import async_session_factory


def test_config_initialization():
    """Test that gateway config loads correctly."""
    from gateway.config import settings
    assert settings is not None
    assert settings.port == 8001


def test_database_settings():
    """Test that database settings are present."""
    from gateway.config import settings
    assert settings.postgres_url is not None
    assert settings.redis_url is not None


def test_storage_models_import():
    """Test that storage models import correctly."""
    from gateway.storage.models import Session as DbSession
    from gateway.storage.models import SessionEvent, Feedback, SourceHealth
    assert DbSession is not None
    assert SessionEvent is not None
    assert Feedback is not None
    assert SourceHealth is not None
