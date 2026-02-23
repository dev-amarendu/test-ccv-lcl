"""Test API health endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api_service.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_returns_ok_when_db_up(client: TestClient):
    """GET /health should return 200 with status ok when DB is accessible."""
    with patch("api_service.routes.health.get_firestore_client") as mock_get_db:
        # Mock successful collection list
        mock_db = MagicMock()
        mock_db.collections.return_value = []
        mock_get_db.return_value = mock_db
        
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "ccv-api"


def test_health_returns_error_when_db_down(client: TestClient):
    """GET /health should return 503 when DB access fails."""
    with patch("api_service.routes.health.get_firestore_client") as mock_get_db:
        # Mock DB failure
        mock_db = MagicMock()
        mock_db.collections.side_effect = Exception("DB Connection Failed")
        mock_get_db.return_value = mock_db
        
        resp = client.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "error"
        assert "DB Connection Failed" in data["detail"]


def test_version_returns_version(client: TestClient):
    """GET /version should return 200 with version string."""
    resp = client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert data["version"] == "0.1.0"


def test_health_has_request_id_header(client: TestClient):
    """Response should include X-Request-Id header."""
    with patch("api_service.routes.health.get_firestore_client") as mock_get_db:
        mock_db = MagicMock()
        mock_db.collections.return_value = []
        mock_get_db.return_value = mock_db
        
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers


def test_health_propagates_request_id(client: TestClient):
    """When X-Request-Id is sent, it should be echoed back."""
    with patch("api_service.routes.health.get_firestore_client") as mock_get_db:
        mock_db = MagicMock()
        mock_db.collections.return_value = []
        mock_get_db.return_value = mock_db
        
        rid = "test-rid-12345"
        resp = client.get("/health", headers={"X-Request-Id": rid})
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == rid
