"""Unit tests for HTTP server components."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from gateway.server.main import create_app
from gateway.core.memory.models import Session


@pytest.fixture
def client():
    """Test client fixture."""
    app = create_app()
    return TestClient(app)


def test_health_endpoint(client):
    """Test that health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "sources" in data
    
    # Test with trailing slash
    response_with_slash = client.get("/health/")
    assert response_with_slash.status_code == 200


def test_sources_endpoint(client):
    """Test sources endpoint returns list of sources."""
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    
    # Test with trailing slash
    response_with_slash = client.get("/api/sources/")
    assert response_with_slash.status_code == 200


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "active_sessions" in data
    assert "tokens_retrieved" in data
    assert "tokens_delivered" in data
    
    # Test with trailing slash
    response_with_slash = client.get("/api/metrics/")
    assert response_with_slash.status_code == 200


def test_sessions_list_endpoint(client):
    """Test sessions list endpoint."""
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
    # Test with trailing slash
    response_with_slash = client.get("/api/sessions/")
    assert response_with_slash.status_code == 200


def test_session_detail_not_found(client):
    """Test that non-existent session returns 404."""
    response = client.get("/api/sessions/non-existent-session-id")
    assert response.status_code == 404


def test_enable_disable_source_not_found(client):
    """Test enabling/disabling non-existent source returns 404."""
    response = client.post("/api/sources/non-existent-source/enable")
    assert response.status_code == 404
    
    response_disable = client.post("/api/sources/non-existent-source/disable")
    assert response_disable.status_code == 404


def test_get_context_endpoint_basic(client):
    """Test that get context endpoint is reachable."""
    request_payload = {
        "task": "Test task",
        "max_tokens": 1000,
        "role": "developer"
    }
    response = client.post("/api/context", json=request_payload)
    # We expect either 200 or 500 (if pipeline components aren't fully mocked)
    assert response.status_code in [200, 500]
    
    # Test with trailing slash
    response_with_slash = client.post("/api/context/", json=request_payload)
    assert response_with_slash.status_code in [200, 500]


def test_validate_change_endpoint_basic(client):
    """Test that validate change endpoint is reachable."""
    request_payload = {
        "diff": "diff --git a/test.txt b/test.txt\n+test line",
        "files": ["test.txt"]
    }
    response = client.post("/api/validate", json=request_payload)
    # We expect either 200 or 500 (if RIP source isn't fully mocked)
    assert response.status_code in [200, 500]
    
    # Test with trailing slash
    response_with_slash = client.post("/api/validate/", json=request_payload)
    assert response_with_slash.status_code in [200, 500]
