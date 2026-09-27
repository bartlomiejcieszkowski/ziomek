import pytest
from fastapi.testclient import TestClient
from ziomek.server import create_app


@pytest.fixture
def client():
    app = create_app()
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


def test_generate_returns_503_without_model(client):
    """Verify /api/tts/generate returns 503 when model not loaded."""
    resp = client.post("/api/tts/generate", json={"text": "test"})
    assert resp.status_code == 503
    data = resp.json()
    assert "error" in data
