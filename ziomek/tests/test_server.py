import pytest
from fastapi.testclient import TestClient
from ziomek.server import create_app


@pytest.fixture
def client():
    app = create_app()
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
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "ziomek"
    assert data["version"] == "0.1.0"


def test_cors(client):
    """Verify CORS headers present on regular requests."""
    resp = client.get("/api/tts/status", headers={"Origin": "http://example.com"})
    assert resp.status_code == 200
    assert "Access-Control-Allow-Origin" in resp.headers
