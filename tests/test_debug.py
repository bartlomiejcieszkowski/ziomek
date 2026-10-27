"""Tests for debug endpoints (dev mode only)."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from ziomek import server


@pytest.fixture
def client_with_dev():
    """Create a test client with dev mode enabled."""
    from ziomek.config import Settings
    settings = Settings(no_gamepad=True)
    app = server.create_app(settings, dev_mode=True)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_without_dev():
    """Create a test client with dev mode disabled."""
    app = server.create_app(dev_mode=False)
    with TestClient(app) as c:
        yield c


class TestDebugEndpoints:
    """Tests for /api/debug/* endpoints (dev mode only)."""

    def test_debug_state_endpoint(self, client_with_dev):
        resp = client_with_dev.get("/api/debug/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "tts_model_ready" in data
        assert "audio_backend" in data
        assert "audio_device" in data
        assert "state_machine_initialized" in data
        assert "stt_engine_initialized" in data
        assert "gamepad_manager_initialized" in data

    def test_debug_state_has_uptime(self, client_with_dev):
        resp = client_with_dev.get("/api/debug/state")
        data = resp.json()
        assert isinstance(data["uptime_seconds"], float)
        assert data["uptime_seconds"] >= 0

    def test_debug_state_has_audio_info(self, client_with_dev):
        resp = client_with_dev.get("/api/debug/state")
        data = resp.json()
        assert isinstance(data["audio_backend"], str)
        assert data["audio_backend"] in ("noop", "sounddevice", "pygame", "pyaudio", "playsound")

    def test_debug_cache_endpoint(self, client_with_dev):
        resp = client_with_dev.get("/api/debug/cache")
        assert resp.status_code == 200
        data = resp.json()
        assert "cache_dir" in data
        assert "size_mb" in data
        assert "files" in data

    def test_debug_config_endpoint(self, client_with_dev):
        resp = client_with_dev.get("/api/debug/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "host" in data
        assert "port" in data
        assert "audio_backend" in data
        assert "stt_engine" in data

    def test_debug_logs_endpoint(self, client_with_dev):
        resp = client_with_dev.get("/api/debug/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_debug_logs_endpoint_with_limit(self, client_with_dev):
        resp = client_with_dev.get("/api/debug/logs?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) <= 10

    def test_debug_logs_clear(self, client_with_dev):
        # Clear logs
        resp = client_with_dev.post("/api/debug/logs/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cleared"

        # Verify logs are cleared
        resp = client_with_dev.get("/api/debug/logs")
        data = resp.json()
        assert len(data["entries"]) == 0

    def test_debug_config_reload(self, client_with_dev):
        resp = client_with_dev.post("/api/debug/config/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reloaded"
        assert "config_path" in data

    def test_debug_page(self, client_with_dev):
        resp = client_with_dev.get("/debug")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "ziomek Debug" in resp.text


class TestDebugEndpointsDisabled:
    """Tests that debug endpoints are not accessible in non-dev mode."""

    def test_debug_state_not_available(self, client_without_dev):
        resp = client_without_dev.get("/api/debug/state")
        assert resp.status_code == 404

    def test_debug_cache_not_available(self, client_without_dev):
        resp = client_without_dev.get("/api/debug/cache")
        assert resp.status_code == 404

    def test_debug_page_not_available(self, client_without_dev):
        resp = client_without_dev.get("/debug")
        assert resp.status_code == 404
