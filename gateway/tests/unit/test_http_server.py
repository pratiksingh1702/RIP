"""Unit tests for HTTP server components."""

import pytest
from fastapi.testclient import TestClient

from gateway.server.main import create_app


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


def test_sources_endpoint(client):
    """Test sources endpoint returns list of sources."""
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/api/metrics")
    assert response.status_code == 200
