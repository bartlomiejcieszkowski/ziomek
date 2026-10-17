"""Tests for STT engine reconfigure functionality."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from ziomek.stt import STTEngine, STTState

logger = logging.getLogger(__name__)


class TestSTTEngineReconfigure:
    """Tests for STTEngine.reconfigure() method."""

    def test_reconfigure_changes_model(self):
        """Reconfigure changes engine and model."""
        engine = STTEngine(engine_name="faster_whisper", model_name="tiny.en")
        with patch("RealtimeSTT.AudioToTextRecorder"):
            success, message = engine.reconfigure("faster_whisper", "base.en")
            assert success is True
            assert "base.en" in message

    def test_reconfigure_changes_engine(self):
        """Reconfigure changes engine type."""
        engine = STTEngine(engine_name="faster_whisper", model_name="tiny.en")
        with patch("RealtimeSTT.AudioToTextRecorder"):
            success, message = engine.reconfigure("whisper_cpp", "tiny.en")
            assert success is True
            assert "whisper_cpp" in message

    def test_reconfigure_invalid_engine(self):
        """Reconfigure with unsupported engine returns failure."""
        engine = STTEngine(engine_name="faster_whisper", model_name="tiny.en")
        with patch("RealtimeSTT.AudioToTextRecorder", side_effect=RuntimeError("boom")):
            success, message = engine.reconfigure("invalid_engine", "tiny.en")
            assert success is False
            assert "Failed to reconfigure" in message

    def test_reconfigure_invalid_model(self):
        """Reconfigure with unsupported model returns failure."""
        engine = STTEngine(engine_name="faster_whisper", model_name="tiny.en")
        with patch("RealtimeSTT.AudioToTextRecorder", side_effect=RuntimeError("boom")):
            success, message = engine.reconfigure("faster_whisper", "nonexistent_model")
            assert success is False
            assert "Failed to reconfigure" in message

    def test_reconfigure_preserves_previous_on_failure(self):
        """Reconfigure failure preserves previous engine/model."""
        engine = STTEngine(engine_name="faster_whisper", model_name="tiny.en")
        with patch("RealtimeSTT.AudioToTextRecorder", side_effect=RuntimeError("boom")):
            success, message = engine.reconfigure("faster_whisper", "base.en")
            assert success is False
            # Verify previous config is preserved
            assert engine._engine_name == "faster_whisper"
            assert engine._model_name == "tiny.en"

    def test_reconfigure_stops_recording(self):
        """Reconfigure stops active recording."""
        engine = STTEngine(engine_name="faster_whisper", model_name="tiny.en")
        # Manually set recording active
        engine._recording_active = True
        mock_recorder = MagicMock()
        engine._recorder = mock_recorder

        with patch("RealtimeSTT.AudioToTextRecorder"):
            success, _ = engine.reconfigure("faster_whisper", "base.en")
            assert success is True
            assert engine._recording_active is False
            mock_recorder.stop.assert_called_once()

    def test_reconfigure_resets_state_to_idle(self):
        """Reconfigure resets STT state to idle."""
        engine = STTEngine(engine_name="faster_whisper", model_name="tiny.en")
        with patch("RealtimeSTT.AudioToTextRecorder"):
            engine.reconfigure("faster_whisper", "base.en")
        assert engine.state == STTState.IDLE

    def test_reconfigure_updates_stats(self):
        """Reconfigure updates stats with new engine/model."""
        engine = STTEngine(engine_name="faster_whisper", model_name="tiny.en")
        with patch("RealtimeSTT.AudioToTextRecorder"):
            engine.reconfigure("faster_whisper", "base.en")
        assert engine.stats.engine_name == "faster_whisper"
        assert engine.stats.model_name == "base.en"
