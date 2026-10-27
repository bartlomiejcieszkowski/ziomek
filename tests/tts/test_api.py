import pytest
from fastapi.testclient import TestClient

from ziomek.server import create_app


@pytest.fixture
def client():
    from ziomek.config import Settings

    settings = Settings(no_gamepad=True)
    app = create_app(settings)
    return TestClient(app)


def test_tts_status(client):
    """Verify /api/tts/status returns ready field."""
    resp = client.get("/api/tts/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "ready" in data


def test_list_voices(client):
    """Verify /api/tts/voices returns voice list."""
    resp = client.get("/api/tts/voices")
    assert resp.status_code == 200
    data = resp.json()
    assert "voices" in data
    assert "default" in data
    assert data["default"] == "cosette"


def test_generate_loads_model_and_returns_200(client):
    """Verify /api/tts/generate loads model lazily and returns audio."""
    resp = client.post("/api/tts/generate", json={"text": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "audio_b64" in data
    assert "duration" in data
    assert "sample_rate" in data
