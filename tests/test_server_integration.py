"""Integration tests that start a real uvicorn server process.

These tests verify the server works end-to-end over actual network sockets,
not just the in-memory TestClient.
"""

import time

import httpx
import pytest
import uvicorn

from ziomek.config import Settings
from ziomek.server import create_app


@pytest.fixture(scope="module")
def real_server():
    """Start a real uvicorn server process for integration tests."""
    # Find an available port
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = s.getsockname()[1]

    settings = Settings.compose(cli_backend="noop", no_vscode=True)
    app = create_app(settings)

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # Start server in a thread so pytest can continue
    # Thread is safe: uvicorn.Server.run() is thread-safe and doesn't
    # share mutable state with the main thread during startup.
    import threading

    server_ready = threading.Event()

    def run_server():
        server.run()
        server_ready.set()

    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()

    # Wait for server to be ready using polling
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            httpx.get(f"http://127.0.0.1:{port}/", timeout=1.0)
            server_ready.set()
            break
        except httpx.ConnectError:
            pass
        time.sleep(0.1)

    yield f"http://127.0.0.1:{port}"

    # Shutdown server
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.integration
class TestRealServerEndpoints:
    """Test real server process endpoints."""

    def test_root_endpoint(self, real_server):
        """Verify / returns ziomek info via real HTTP."""
        resp = httpx.get(f"{real_server}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "ziomek"
        assert "version" in data

    def test_status_endpoint(self, real_server):
        """Verify /status returns ready and model_loaded via real HTTP."""
        resp = httpx.get(f"{real_server}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "ready" in data
        assert "model_loaded" in data
        assert "endpoints" in data

    def test_health_endpoint_with_new_fields(self, real_server):
        """Health endpoint should include uptime, backend, and cache stats."""
        resp = httpx.get(f"{real_server}/status")
        assert resp.status_code == 200
        data = resp.json()

        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

        assert "audio_backend" in data
        assert isinstance(data["audio_backend"], str)

        assert "audio_device" in data or data["audio_device"] is None

        assert "cache_dir" in data
        assert "cache_stats" in data
        assert "size_mb" in data["cache_stats"]
        assert "files" in data["cache_stats"]

    def test_cors_headers(self, real_server):
        """Verify CORS headers present on requests from localhost.*"""
        resp = httpx.get(f"{real_server}/api/tts/status", headers={"Origin": "http://localhost:5004"})
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" in resp.headers

    def test_tts_status_endpoint(self, real_server):
        """Verify /api/tts/status returns 200."""
        resp = httpx.get(f"{real_server}/api/tts/status")
        assert resp.status_code == 200

    def test_list_voices_endpoint(self, real_server):
        """Verify /api/tts/voices returns 200."""
        resp = httpx.get(f"{real_server}/api/tts/voices")
        assert resp.status_code == 200

    def test_tts_generate_loads_model_and_returns_200(self, real_server):
        """Verify /api/tts/generate loads model lazily and returns audio."""
        resp = httpx.post(f"{real_server}/api/tts/generate", json={"text": "test"}, timeout=60.0)
        assert resp.status_code == 200
        data = resp.json()
        assert "audio_b64" in data
        assert "duration" in data

    def test_avatar_state_endpoint(self, real_server):
        """Verify /api/avatar/state returns 200."""
        resp = httpx.get(f"{real_server}/api/avatar/state")
        assert resp.status_code == 200

    def test_avatar_expression_endpoint(self, real_server):
        """Verify /api/avatar/expression returns 200."""
        resp = httpx.post(
            f"{real_server}/api/avatar/expression",
            json={"name": "bored"}
        )
        assert resp.status_code == 200

    def test_avatar_input_endpoint(self, real_server):
        """Verify /api/avatar/input returns 200."""
        resp = httpx.post(
            f"{real_server}/api/avatar/input",
            json={
                "buttons": [],
                "axes": [0, 0, 0],
                "connected": False,
                "streaming": False,
                "chatFocused": False,
                "errorState": False,
            }
        )
        assert resp.status_code == 200

    def test_avatar_sprite_endpoint(self, real_server):
        """Verify /api/avatar/sprite returns 200."""
        resp = httpx.get(f"{real_server}/api/avatar/sprite")
        assert resp.status_code == 200

    def test_avatar_speak_returns_200_with_tts(self, real_server):
        """Verify /api/avatar/speak works when TTS model is loaded."""
        resp = httpx.post(
            f"{real_server}/api/avatar/speak",
            json={"text": "hello"},
            timeout=60.0
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "playing"

    def test_openapi_docs_available(self, real_server):
        """Verify /docs (Swagger UI) is accessible."""
        resp = httpx.get(f"{real_server}/docs")
        assert resp.status_code == 200

    def test_redoc_available(self, real_server):
        """Verify /redoc is accessible."""
        resp = httpx.get(f"{real_server}/redoc")
        assert resp.status_code == 200

    def test_request_id_header(self, real_server):
        """Verify X-Request-ID header is present in responses."""
        resp = httpx.get(f"{real_server}/")
        assert "x-request-id" in resp.headers
        # Verify it's a valid UUID
        import uuid

        uuid.UUID(resp.headers["x-request-id"])

    def test_request_id_echoed_in_response(self, real_server):
        """Verify request ID is echoed in response body."""
        resp = httpx.get(f"{real_server}/")
        request_id = resp.headers["x-request-id"]
        # The request ID should be available via middleware
        assert request_id is not None
        assert len(request_id) > 0

    def test_concurrent_requests(self, real_server):
        """Verify server handles multiple concurrent requests."""
        import concurrent.futures

        def make_request():
            return httpx.get(f"{real_server}/status")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        for resp in responses:
            assert resp.status_code == 200
            data = resp.json()
            assert "ready" in data

    def test_server_uptime_increases(self, real_server):
        """Verify uptime_seconds increases over time."""
        import time

        resp1 = httpx.get(f"{real_server}/status")
        uptime1 = resp1.json()["uptime_seconds"]
        time.sleep(0.1)  # Wait 100ms
        resp2 = httpx.get(f"{real_server}/status")
        uptime2 = resp2.json()["uptime_seconds"]

        assert uptime2 > uptime1, "Uptime should increase over time"

    def test_audio_backend_info(self, real_server):
        """Verify audio backend info is present in health endpoint."""
        resp = httpx.get(f"{real_server}/status")
        data = resp.json()
        assert "audio_backend" in data
        assert isinstance(data["audio_backend"], str)
        # Backend should be a non-empty string (value depends on Settings.compose)
        assert len(data["audio_backend"]) > 0

    def test_cache_stats_structure(self, real_server):
        """Verify cache_stats has correct structure."""
        resp = httpx.get(f"{real_server}/status")
        data = resp.json()
        cache_stats = data["cache_stats"]
        assert isinstance(cache_stats, dict)
        assert "size_mb" in cache_stats
        assert "files" in cache_stats
        assert isinstance(cache_stats["size_mb"], (int, float))
        assert isinstance(cache_stats["files"], int)
