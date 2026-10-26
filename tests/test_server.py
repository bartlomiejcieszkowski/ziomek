import pytest
from fastapi.testclient import TestClient

from ziomek.server import create_app


@pytest.fixture
def client():
    from ziomek.config import Settings

    settings = Settings(no_vscode=True)
    app = create_app(settings)
    return TestClient(app)


def test_status(client):
    """Verify /status returns ready and model_loaded fields."""
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "ready" in data
    assert "model_loaded" in data
    assert "endpoints" in data


def test_root(client):
    """Verify / returns ziomek info."""
    from ziomek import __version__

    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "ziomek"
    assert data["version"] == __version__


def test_cors(client):
    """Verify CORS headers present on requests from localhost.*"""
    resp = client.get("/api/tts/status", headers={"Origin": "http://localhost:5004"})
    assert resp.status_code == 200
    assert "Access-Control-Allow-Origin" in resp.headers


def test_health_status_has_new_fields():
    """Health endpoint should include uptime, backend, and cache stats."""
    from fastapi.testclient import TestClient

    from ziomek.config import Settings
    from ziomek.server import create_app

    settings = Settings(no_vscode=True)
    app = create_app(settings)
    client = TestClient(app)
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()

    # Verify new fields exist and have correct types
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0

    assert "audio_backend" in data
    assert isinstance(data["audio_backend"], str)

    assert "audio_device" in data
    assert data["audio_device"] is None or isinstance(data["audio_device"], (str, int))

    assert "cache_dir" in data

    assert "cache_stats" in data
    assert isinstance(data["cache_stats"], dict)
    assert "size_mb" in data["cache_stats"]
    assert "files" in data["cache_stats"]


def test_health_status_null_when_model_not_loaded():
    """When TTS model is not loaded, model_loaded should be False."""
    from fastapi.testclient import TestClient

    from ziomek.config import Settings
    from ziomek.server import create_app

    settings = Settings(no_vscode=True)
    app = create_app(settings)
    client = TestClient(app)
    resp = client.get("/status")
    data = resp.json()
    # Should not crash even if model is None
    assert isinstance(data["model_loaded"], bool)
    assert isinstance(data["ready"], bool)


def test_create_app_skips_stt_when_extra_missing():
    """The STT engine must not be created when the 'stt' extra is not installed."""
    from unittest.mock import patch

    from ziomek import server
    from ziomek.config import Settings
    from ziomek.server import create_app

    settings = Settings(no_vscode=True)
    with patch("ziomek.server.stt_installed", return_value=False):
        app = create_app(settings)

    assert app is not None
    assert server._stt_engine is None
