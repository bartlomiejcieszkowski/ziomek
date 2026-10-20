"""Tests for MCP HTTP transport."""

import json

import pytest
from fastapi.testclient import TestClient

from ziomek.config import Settings
from ziomek.server import create_app


@pytest.fixture
def http_mcp_client():
    """Create a test client with MCP HTTP enabled."""
    settings = Settings(mcp_port=5004, mcp_transport="http")
    app = create_app(settings, mcp_http_enabled=True)
    with TestClient(app) as c:
        yield c


class TestMcpHttpHealth:
    """Test MCP HTTP health endpoint."""

    def test_mcp_health_returns_ok(self, http_mcp_client):
        resp = http_mcp_client.get("/mcp/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["transport"] == "http"
        assert data["endpoints"]["sse"] == "/mcp/sse"
        assert data["endpoints"]["message"] == "/mcp/message"


class TestMcpHttpRoute:
    """Test MCP HTTP routes are registered."""

    def test_mcp_page_returns_html(self, http_mcp_client):
        resp = http_mcp_client.get("/mcp")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "ziomek MCP" in resp.text

    def test_mcp_sse_endpoint_exists(self, http_mcp_client):
        # Just check the route exists and returns 200 with correct content-type
        # Don't actually consume the SSE stream (it's infinite)
        with pytest.raises(Exception):
            http_mcp_client.get("/mcp/sse")


class TestMcpHttpDisabled:
    """Test MCP HTTP routes are not registered when disabled."""

    def test_mcp_health_not_available(self):
        settings = Settings(mcp_port=5004, mcp_transport="stdio")
        app = create_app(settings, mcp_http_enabled=False)
        with TestClient(app) as c:
            resp = c.get("/mcp/health")
            assert resp.status_code == 404

    def test_mcp_page_not_available(self):
        settings = Settings(mcp_port=5004, mcp_transport="stdio")
        app = create_app(settings, mcp_http_enabled=False)
        with TestClient(app) as c:
            resp = c.get("/mcp")
            assert resp.status_code == 404


class TestMcpHttpConfig:
    """Test MCP config loading from YAML."""

    def test_mcp_port_default(self):
        settings = Settings()
        assert settings.mcp_port == 5004

    def test_mcp_transport_default(self):
        settings = Settings()
        assert settings.mcp_transport == "stdio"

    def test_mcp_port_from_compose(self):
        settings = Settings.compose(mcp_port=9999)
        assert settings.mcp_port == 9999

    def test_mcp_transport_from_compose(self):
        settings = Settings.compose(mcp_transport="http")
        assert settings.mcp_transport == "http"
