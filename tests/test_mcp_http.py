"""Tests for MCP HTTP transport routing."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from ziomek import __version__
from ziomek.mcp import set_expose_full_config
from ziomek.mcp.http import create_http_app, register_mcp_http_routes

# Accept both so the transport can answer with JSON or SSE.
RPC_HEADERS = {"Accept": "application/json, text/event-stream"}
ALIASES = ("/mcp/sse", "/mcp/message")


def _mock_settings():
    """Settings stand-in so the config resource has something to read."""
    settings = MagicMock()
    settings.host = "localhost"
    settings.port = 5004
    settings.voice = "cosette"
    settings.cache_dir = "/tmp/cache"
    settings.log_level = "INFO"
    settings.stt_engine = "faster_whisper"
    settings.stt_model = "tiny.en"
    settings.stt_model_dir = "/tmp/models"
    settings.model_path = None
    return settings


def _client(app) -> TestClient:
    """TestClient on a localhost host so transport security accepts the request."""
    return TestClient(app, base_url="http://localhost")


def _payload(response):
    """Read a JSON-RPC result from either a JSON or an SSE response body."""
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in response.text.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        raise AssertionError(f"No JSON-RPC message in SSE body: {response.text!r}")
    return response.json()


def _rpc(client, path, body, session_id=None):
    headers = {**RPC_HEADERS, "content-type": "application/json"}
    if session_id:
        headers["mcp-session-id"] = session_id
    return client.post(path, headers=headers, json=body)


def _initialize_request(client, path="/mcp"):
    return _rpc(
        client,
        path,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.0.0"},
            },
        },
    )


def _session(client, path="/mcp"):
    """Open a session and return its id; requests without one are rejected with 400."""
    session_id = _initialize_request(client, path).headers.get("mcp-session-id")
    assert session_id, f"expected a session id for {path}"
    return session_id


class TestMcpTransportRouting:
    """The handler is path-agnostic, so aliases must reach the same session manager."""

    def test_initialize_on_canonical_path(self):
        app = create_http_app()
        with _client(app) as client:
            response = _initialize_request(client)
            assert response.status_code == 200
            assert _payload(response)["result"]["capabilities"]

    def test_alias_paths_reach_the_same_session(self):
        """A session opened on /mcp must be served by the alias routes too."""
        app = create_http_app()
        with _client(app) as client:
            session_id = _initialize_request(client).headers.get("mcp-session-id")
            assert session_id, "expected a session id on the opening request"

            for path in ALIASES:
                response = _rpc(
                    client,
                    path,
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                    session_id=session_id,
                )
                assert response.status_code == 200, f"{path} did not route to the session manager"
                assert response.headers.get("mcp-session-id") == session_id

    def test_routes_work_when_registered_on_the_main_app(self):
        app = FastAPI()
        register_mcp_http_routes(app)
        with _client(app) as client:
            session_id = _initialize_request(client).headers.get("mcp-session-id")
            assert session_id
            for path in ALIASES:
                response = _rpc(
                    client,
                    path,
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                    session_id=session_id,
                )
                assert response.status_code == 200, f"{path} is not routed to the session manager"


class TestMcpHealthAndInfo:
    """Health advertises the canonical path and the aliases; info lives on its own path."""

    def test_health_advertises_transport_and_aliases(self):
        app = create_http_app()
        with _client(app) as client:
            data = client.get("/mcp/health").json()
            assert data["status"] == "ok"
            assert data["transport"] == "http"
            assert data["endpoints"]["mcp"] == "/mcp"
            for path in ALIASES:
                assert data["endpoints"][path.rsplit("/", 1)[-1]] == path

    def test_info_page_is_not_on_the_transport_path(self):
        app = create_http_app()
        with _client(app) as client:
            html = client.get("/mcp/info")
            assert html.status_code == 200
            assert "ziomek MCP Server" in html.text
            # The transport path serves JSON-RPC, not an HTML page.
            rpc = _initialize_request(client)
            assert "text/html" not in rpc.headers.get("content-type", "")

    def test_server_info_version_matches_the_package(self):
        app = create_http_app()
        with _client(app) as client:
            response = _initialize_request(client)
            server_info = _payload(response)["result"]["serverInfo"]
            assert server_info["version"] == __version__


class TestMcpResources:
    """Resource handlers still work over the HTTP transport."""

    def test_list_resources(self):
        app = create_http_app()
        with _client(app) as client:
            session_id = _session(client)
            data = _payload(
                _rpc(
                    client,
                    "/mcp",
                    {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}},
                    session_id=session_id,
                )
            )
            uris = [r["uri"] for r in data["result"]["resources"]]
            assert "voices://" in uris
            assert "models://" in uris
            assert "expressions://" in uris
            assert "config://" in uris

    def test_read_config_readonly(self):
        """Config resource is read-only by default and does not mark itself as fully exposed."""
        app = create_http_app()
        set_expose_full_config(False)
        try:
            with _client(app) as client, patch("ziomek.server._settings", _mock_settings()):
                session_id = _session(client)
                data = _payload(
                    _rpc(
                        client,
                        "/mcp",
                        {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "config://"}},
                        session_id=session_id,
                    )
                )
                content = json.loads(data["result"]["contents"][0]["text"])
                assert content["port"] == 5004
                assert "full_config" not in content
        finally:
            set_expose_full_config(False)

    def test_read_config_full(self):
        """With the expose flag the config is marked as fully exposed."""
        app = FastAPI()
        register_mcp_http_routes(app, expose_full_config=True)
        try:
            with _client(app) as client, patch("ziomek.server._settings", _mock_settings()):
                session_id = _session(client)
                data = _payload(
                    _rpc(
                        client,
                        "/mcp",
                        {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "config://"}},
                        session_id=session_id,
                    )
                )
                content = json.loads(data["result"]["contents"][0]["text"])
                assert content["full_config"] is True
        finally:
            set_expose_full_config(False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
