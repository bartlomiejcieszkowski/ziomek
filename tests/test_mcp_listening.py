"""ziomek MCP listening session tests."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from ziomek.mcp.listening import ListeningSession


class TestListeningSessionStartStop:
    """Test starting and stopping a listening session."""

    def test_session_starts(self):
        """Session starts successfully."""
        with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
            mock_instance = MagicMock()
            MockEngine.return_value = mock_instance

            session = ListeningSession()
            success = session.start()
            assert success is True
            assert session.is_active is True
            mock_instance.start_recording.assert_called_once()

    def test_session_double_start_fails(self):
        """Starting an active session returns False."""
        with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
            mock_instance = MagicMock()
            MockEngine.return_value = mock_instance

            session = ListeningSession()
            session.start()
            success = session.start()
            assert success is False

    def test_session_stops(self):
        """Session stops successfully."""
        with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
            mock_instance = MagicMock()
            MockEngine.return_value = mock_instance

            session = ListeningSession()
            session.start()
            success = session.stop()
            assert success is True
            assert session.is_active is False
            mock_instance.stop_recording.assert_called_once()

    def test_stop_inactive_session(self):
        """Stopping an inactive session returns False."""
        session = ListeningSession()
        success = session.stop()
        assert success is False

    def test_session_stops_engine(self):
        """Stopping session shuts down the STT engine."""
        with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
            mock_instance = MagicMock()
            MockEngine.return_value = mock_instance

            session = ListeningSession()
            session.start()
            assert session._engine is not None
            session.stop()
            assert session._engine is None


class TestListeningSessionResult:
    """Test transcription result retrieval."""

    def test_get_result_empty(self):
        """Empty result before any transcription."""
        session = ListeningSession()
        result = session.get_result()
        assert result["text"] == ""
        assert result["is_final"] is False
        assert result["state"] == "idle"

    def test_get_result_returns_latest(self):
        """Result returns latest transcription."""
        from ziomek.stt import STTResult, STTState

        with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
            mock_instance = MagicMock()
            MockEngine.return_value = mock_instance

            session = ListeningSession()
            session.start()

            # Simulate a transcription result
            result = STTResult(
                text="hello world",
                is_final=True,
                realtime=False,
            )
            session._on_transcription(result)

            retrieved = session.get_result()
            assert retrieved["text"] == "hello world"
            assert retrieved["is_final"] is True
            assert retrieved["state"] == "listening"

    def test_get_result_after_stop(self):
        """Result state changes to idle after stop."""
        from ziomek.stt import STTResult, STTState

        with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
            mock_instance = MagicMock()
            MockEngine.return_value = mock_instance

            session = ListeningSession()
            session.start()

            result = STTResult(
                text="hello world",
                is_final=True,
                realtime=False,
            )
            session._on_transcription(result)
            session.stop()

            retrieved = session.get_result()
            assert retrieved["state"] == "idle"


class TestListeningSessionThreadSafety:
    """Test thread-safe access to session state."""

    def test_concurrent_get_result(self):
        """Multiple threads can read results concurrently."""
        with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
            mock_instance = MagicMock()
            MockEngine.return_value = mock_instance

            session = ListeningSession()
            session.start()

            errors = []

            def read_results():
                try:
                    for _ in range(100):
                        session.get_result()
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=read_results) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0

    def test_concurrent_start_stop(self):
        """Start/stop operations are thread-safe."""
        with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
            mock_instance = MagicMock()
            MockEngine.return_value = mock_instance

            session = ListeningSession()

            def start_stop():
                for _ in range(10):
                    session.start()
                    time.sleep(0.01)
                    session.stop()

            threads = [threading.Thread(target=start_stop) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Final state should be inactive
            assert session.is_active is False
