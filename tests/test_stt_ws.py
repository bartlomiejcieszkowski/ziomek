"""Tests for STT WebSocket endpoint."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_mock_stt_engine():
    """Create a mock STT engine for testing."""
    mock = MagicMock()
    mock.state.value = "idle"
    mock.stats.engine_name = "faster_whisper"
    mock.stats.model_name = "tiny.en"
    mock.stats.state.value = "idle"
    mock.stats.transcription_count = 0

    def start_recording():
        mock.state.value = "listening"
        mock.stats.state.value = "listening"

    def stop_recording():
        mock.state.value = "idle"
        mock.stats.state.value = "idle"

    mock.start_recording = MagicMock(side_effect=start_recording)
    mock.stop_recording = MagicMock(side_effect=stop_recording)
    return mock


class TestSTTWebSocket:
    """Tests for WS /api/stt/stream."""

    @pytest.fixture
    def client(self):
        """Create a test client with a mocked STT engine."""
        mock = _make_mock_stt_engine()
        with patch("ziomek.server.STTEngine", return_value=mock):
            from ziomek.server import create_app
            from ziomek.config import Settings

            settings = Settings(no_vscode=False)
            app = create_app(settings)
            yield TestClient(app)

    def test_websocket_connect(self, client):
        """WebSocket endpoint accepts connections."""
        with client.websocket_connect("/api/stt/stream") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "session_id" in data

    def test_websocket_start_command(self, client):
        """Client can send start command via WebSocket."""
        with client.websocket_connect("/api/stt/stream") as ws:
            ws.receive_json()  # consume 'connected' message
            ws.send_json({"action": "start"})
            data = ws.receive_json()
            assert data["type"] == "status"
            assert data["state"] == "listening"

    def test_websocket_stop_command(self, client):
        """Client can send stop command via WebSocket."""
        with client.websocket_connect("/api/stt/stream") as ws:
            ws.receive_json()  # consume 'connected' message
            ws.send_json({"action": "start"})
            ws.receive_json()  # status response
            ws.send_json({"action": "stop"})
            data = ws.receive_json()
            assert data["type"] == "status"
            assert data["state"] == "idle"

    def test_websocket_status_command(self, client):
        """Client can query status via WebSocket."""
        with client.websocket_connect("/api/stt/stream") as ws:
            ws.receive_json()  # consume 'connected' message
            ws.send_json({"action": "status"})
            data = ws.receive_json()
            assert data["type"] == "status"
            assert "state" in data

    def test_websocket_disconnect(self, client):
        """WebSocket properly handles client disconnect."""
        with client.websocket_connect("/api/stt/stream") as ws:
            pass  # Connection closes here
