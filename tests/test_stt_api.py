"""Tests for STT HTTP API endpoints."""

import base64
import io
import wave

import pytest
from fastapi.testclient import TestClient

from ziomek.config import Settings
from ziomek.server import create_app


@pytest.fixture
def client():
    """Create a test client with STT enabled."""
    settings = Settings(no_vscode=False)  # Enable STT
    app = create_app(settings)
    return TestClient(app)


class TestSTTStatus:
    """Tests for GET /api/stt/status."""

    def test_status_returns_200(self, client):
        """STT status endpoint returns 200."""
        resp = client.get("/api/stt/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data
        assert "engine" in data
        assert "model" in data

    def test_status_initial_state_is_listening(self, client):
        """STT engine starts in LISTENING state (begins recording immediately)."""
        resp = client.get("/api/stt/status")
        data = resp.json()
        assert data["state"] == "listening"

    def test_status_has_engine_name(self, client):
        """Status includes engine name."""
        resp = client.get("/api/stt/status")
        data = resp.json()
        assert data["engine"] == "faster_whisper"


class TestSTTStartStop:
    """Tests for POST /api/stt/start and /api/stt/stop."""

    def test_start_recording(self, client):
        """Starting recording returns 200."""
        resp = client.post("/api/stt/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["state"] == "listening"

    def test_stop_recording(self, client):
        """Stopping recording returns 200."""
        # Start first
        client.post("/api/stt/start")
        resp = client.post("/api/stt/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"
        assert data["state"] == "idle"

    def test_start_when_already_recording(self, client):
        """Starting while already recording returns 409."""
        client.post("/api/stt/start")
        resp = client.post("/api/stt/start")
        assert resp.status_code == 409


class TestSTTModels:
    """Tests for GET /api/stt/models."""

    def test_models_returns_list(self, client):
        """Models endpoint returns available models."""
        resp = client.get("/api/stt/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "tiny.en" in data["models"]
        assert "base.en" in data["models"]
        assert "small.en" in data["models"]

    def test_models_has_default(self, client):
        """Models endpoint includes default."""
        resp = client.get("/api/stt/models")
        data = resp.json()
        assert data["default"] == "tiny.en"


class TestSTTTranscribe:
    """Tests for POST /api/stt/transcribe."""

    def _make_wav_b64(self, duration_ms=100):
        """Create a minimal WAV audio blob for testing."""
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            # Write silent audio
            frames = b'\x00\x00' * (duration_ms * 16 // 1000)
            wav_file.writeframes(frames)
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    def test_transcribe_returns_result(self, client):
        """Transcribe endpoint returns text result."""
        wav_b64 = self._make_wav_b64()
        resp = client.post("/api/stt/transcribe", json={
            "audio_b64": wav_b64,
            "sample_rate": 16000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "is_final" in data
