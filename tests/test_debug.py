"""Tests for debug endpoints (dev mode only)."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from ziomek import debug_report, server


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
        assert data["audio_backend"] in (
            "noop",
            "sounddevice",
            "raw_stream",
            "raw_stream_overlap",
            "pygame",
            "pyaudio",
            "playsound",
        )

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

    def test_a_page_can_post_what_it_measured_and_the_path_keeps_it(self, client_with_dev):
        debug_report.clear()
        resp = client_with_dev.post(
            "/api/debug/render",
            json={"room": {"width": 1580, "height": 1064}, "cell": {"width": 790, "height": 1064}, "frames": 7},
        )
        assert resp.status_code == 200
        assert debug_report.last()["frames"] == 7

    def test_a_report_that_is_not_an_object_is_not_kept(self, client_with_dev):
        debug_report.clear()
        resp = client_with_dev.post("/api/debug/render", json="the page measured a room")
        assert resp.status_code == 400
        assert debug_report.last() is None

    def test_debug_page(self, client_with_dev):
        resp = client_with_dev.get("/debug")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "ziomek Debug" in resp.text
        # A browser asks for an icon on its own when it renders a page, so the page names the
        # path the app answers for instead of the one nothing serves.
        assert '<link rel="icon" href="/favicon.svg">' in resp.text


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

    def test_the_report_path_is_not_open_when_the_server_runs_without_dev_mode(self, client_without_dev):
        debug_report.clear()
        resp = client_without_dev.post("/api/debug/render", json={"room": {"width": 640, "height": 480}})
        assert resp.status_code == 404
        assert debug_report.last() is None
