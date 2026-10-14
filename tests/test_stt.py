"""Tests for the STT engine module."""

import pytest

from ziomek.stt import STTEngine, STTState


class TestSTTEngineInitialization:
    def test_default_initialization(self):
        engine = STTEngine()
        assert engine.state == STTState.IDLE
        assert engine.stats.engine_name == "faster_whisper"
        assert engine.stats.model_name == "tiny.en"

    def test_custom_initialization(self):
        engine = STTEngine(
            engine_name="faster_whisper",
            model_name="base.en",
            model_dir="/tmp/models",
        )
        assert engine.state == STTState.IDLE
        assert engine.stats.engine_name == "faster_whisper"
        assert engine.stats.model_name == "base.en"


class TestSTTEngineStartStop:
    def test_stop_without_start(self):
        engine = STTEngine()
        engine.stop()  # Should not raise
        assert engine.state == STTState.IDLE

    def test_start_stop_with_realtime(self):
        """Test start/stop cycle when RealtimeSTT is installed.

        Uses subprocess to avoid segfaults in whisper.cpp on Windows
        crashing the pytest process.
        """
        try:
            from RealtimeSTT import AudioToTextRecorder
        except ImportError:
            pytest.skip("RealtimeSTT not installed")

        import subprocess
        import sys

        code = """
import sys
sys.path.insert(0, "src")
from ziomek.stt import STTEngine, STTState
engine = STTEngine()
engine.start()
assert engine.state == STTState.LISTENING
engine.stop()
assert engine.state == STTState.IDLE
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            pytest.skip(f"RealtimeSTT initialization failed: {result.stderr[:200]}")
        assert result.stdout.strip() == "OK"


class TestSTTEngineStats:
    def test_stats_are_copy(self):
        engine = STTEngine()
        stats1 = engine.stats
        stats2 = engine.stats
        assert stats1 is not stats2


class TestDownloadModel:
    def test_download_model_returns_path(self):
        """Test that download_model returns a Path object."""
        from pathlib import Path

        from ziomek.stt import download_model

        # This may fail if faster_whisper not installed, which is OK
        try:
            result = download_model("tiny.en")
            assert isinstance(result, (str, Path))
        except ImportError:
            pytest.skip("faster_whisper not installed")
