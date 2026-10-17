"""Tests for STT WebSocket endpoint."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from ziomek.api.stt_ws import _broadcast, _connected_clients, router
from ziomek.stt import STTState

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def clear_ws_clients():
    """Clear WebSocket clients before each test."""
    _connected_clients.clear()
    yield
    _connected_clients.clear()


class TestSTTWebSocket:
    """Tests for STT WebSocket endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from ziomek.config import Settings
        from ziomek.server import create_app

        settings = Settings(no_vscode=True)
        app = create_app(settings=settings, dev_mode=False)
        app.include_router(router)
        return TestClient(app)

    def test_ws_connect(self, client):
        """WebSocket connects and receives session ID."""
        with client.websocket_connect("/api/stt/stream") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "session_id" in data

    def test_ws_send_start(self, client):
        """Client sends start command, receives status."""
        import ziomek.server as server_module
        mock_engine = MagicMock()
        mock_engine.state.value = "recording"
        mock_engine.start_recording = MagicMock()
        server_module._stt_engine = mock_engine

        try:
            with client.websocket_connect("/api/stt/stream") as ws:
                ws.receive_json()  # Consume "connected" message first
                ws.send_json({"action": "start"})
                data = ws.receive_json()
                assert data["type"] == "status"
                assert data["state"] == "recording"
        finally:
            server_module._stt_engine = None

    def test_ws_send_stop(self, client):
        """Client sends stop command, receives status."""
        import ziomek.server as server_module
        mock_engine = MagicMock()
        mock_engine.state.value = "idle"
        mock_engine.stop_recording = MagicMock()
        server_module._stt_engine = mock_engine

        try:
            with client.websocket_connect("/api/stt/stream") as ws:
                ws.receive_json()  # Consume "connected"
                ws.send_json({"action": "stop"})
                data = ws.receive_json()
                assert data["type"] == "status"
                assert data["state"] == "idle"
        finally:
            server_module._stt_engine = None

    def test_ws_send_status(self, client):
        """Client sends status command, receives engine info."""
        import ziomek.server as server_module
        mock_engine = MagicMock()
        mock_engine.stats.engine_name = "faster_whisper"
        mock_engine.stats.model_name = "tiny.en"
        mock_engine.stats.state = STTState.IDLE
        mock_engine.stats.transcription_count = 42
        server_module._stt_engine = mock_engine

        try:
            with client.websocket_connect("/api/stt/stream") as ws:
                ws.receive_json()  # Consume "connected"
                ws.send_json({"action": "status"})
                data = ws.receive_json()
                assert data["type"] == "status"
                assert data["engine"] == "faster_whisper"
                assert data["model"] == "tiny.en"
                assert data["transcription_count"] == 42
        finally:
            server_module._stt_engine = None

    def test_ws_send_reconfigure(self, client):
        """Client sends reconfigure command."""
        import ziomek.server as server_module
        mock_engine = MagicMock()
        mock_engine.reconfigure = MagicMock(return_value=(True, "OK"))
        server_module._stt_engine = mock_engine

        try:
            with client.websocket_connect("/api/stt/stream") as ws:
                ws.receive_json()  # Consume "connected"
                ws.send_json({
                    "action": "reconfigure",
                    "engine": "faster_whisper",
                    "model": "base.en",
                })
                data = ws.receive_json()
                assert data["type"] == "reconfigured"
                assert data["success"] is True
                assert data["engine"] == "faster_whisper"
                assert data["model"] == "base.en"
        finally:
            server_module._stt_engine = None

    def test_ws_unknown_action(self, client):
        """Client sends unknown action, receives error."""
        with client.websocket_connect("/api/stt/stream") as ws:
            ws.receive_json()  # Consume "connected"
            ws.send_json({"action": "unknown"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Unknown action" in data["message"]

    def test_ws_disconnect(self, client):
        """WebSocket disconnect cleans up client list."""
        with client.websocket_connect("/api/stt/stream") as ws:
            ws.receive_json()  # Consume "connected"
            assert len(_connected_clients) == 1

        assert len(_connected_clients) == 0

    def test_ws_no_engine(self, client):
        """Client commands fail gracefully when engine is None."""
        import ziomek.server as server_module
        server_module._stt_engine = None

        with client.websocket_connect("/api/stt/stream") as ws:
            ws.receive_json()  # Consume "connected"
            ws.send_json({"action": "start"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "not initialized" in data["message"]


class TestBroadcast:
    """Tests for _broadcast function."""

    @pytest.fixture(autouse=True)
    def setup_clients(self):
        """Set up mock WebSocket clients."""
        self.mock_client1 = AsyncMock()
        self.mock_client1.send_json = AsyncMock()
        self.mock_client2 = AsyncMock()
        self.mock_client2.send_json = AsyncMock()
        _connected_clients.extend([self.mock_client1, self.mock_client2])
        yield
        _connected_clients.clear()

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        """Broadcast sends message to all connected clients."""
        message = {"type": "transcription", "text": "Hello", "is_final": True}
        await _broadcast(message)

        self.mock_client1.send_json.assert_awaited_once_with(message)
        self.mock_client2.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected(self):
        """Broadcast removes clients that fail to send."""
        self.mock_client1.send_json = AsyncMock(side_effect=RuntimeError("connection lost"))
        self.mock_client2.send_json = AsyncMock()

        message = {"type": "transcription", "text": "Hello", "is_final": True}
        await _broadcast(message)

        assert self.mock_client1 not in _connected_clients
        assert self.mock_client2 in _connected_clients

    @pytest.mark.asyncio
    async def test_broadcast_empty_client_list(self):
        """Broadcast does nothing when no clients connected."""
        _connected_clients.clear()
        message = {"type": "transcription", "text": "Hello", "is_final": True}
        # Should not raise
        await _broadcast(message)
