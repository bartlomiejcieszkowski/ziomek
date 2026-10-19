"""Pytest fixtures for ziomek tests."""

import pytest


@pytest.fixture(autouse=True)
def _cleanup_stt_engine():
    """Stop STT engine after each test to prevent hanging threads."""
    yield
    try:
        from ziomek.server import _stt_engine
        if _stt_engine is not None:
            _stt_engine.stop()
    except Exception:
        pass


@pytest.fixture
def stt_engine_mock(mocker):
    """Mock STTEngine for listening session tests."""
    from unittest.mock import MagicMock, patch

    with patch("ziomek.mcp.listening.STTEngine") as MockEngine:
        mock_instance = MagicMock()
        mock_instance.start_recording = MagicMock()
        mock_instance.stop_recording = MagicMock()
        MockEngine.return_value = mock_instance
        yield mock_instance
