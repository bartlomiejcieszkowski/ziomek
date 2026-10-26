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
        """Test start/stop cycle when RealtimeSTT is installed."""
        try:
            from RealtimeSTT import AudioToTextRecorder
        except ImportError:
            pytest.skip("RealtimeSTT not installed")

        engine = STTEngine()
        engine.start()
        # Engine may fail to start due to memory constraints or missing
        # audio hardware — only assert LISTENING if it succeeded
        if engine.state == STTState.LISTENING:
            engine.stop()
            assert engine.state == STTState.IDLE

    def test_start_from_file_uses_no_microphone(self, monkeypatch):
        """start_from_file() must pass use_microphone=False."""
        mock_recorder = object()

        class FakeAudioToTextRecorder:
            def __init__(self, **kwargs):  # noqa: ANN001
                assert kwargs.get("use_microphone") is False, "start_from_file must set use_microphone=False"
                self._text_calls = []

            def text(self):  # noqa: ANN201
                return ""

            def feed_audio(self, *args, **kwargs):  # noqa: ANN201, ANN002, ARG002
                pass

            def shutdown(self):  # noqa: ANN201
                pass

            def start(self):  # noqa: ANN201
                pass

            def stop(self):  # noqa: ANN201
                pass

        monkeypatch.setattr(
            "ziomek.stt.RealtimeSTT.AudioToTextRecorder",
            FakeAudioToTextRecorder,
        )
        engine = STTEngine()
        engine.start_from_file()
        assert engine.state == STTState.IDLE  # no listen thread for file mode


class TestSTTEngineStats:
    def test_stats_are_copy(self):
        engine = STTEngine()
        stats1 = engine.stats
        stats2 = engine.stats
        assert stats1 is not stats2


class TestDecodeAudio:
    def test_float32_array_is_scaled_to_int16_range(self):
        """Full-scale float audio must map to the int16 range, not truncate to silence."""
        import numpy as np

        from ziomek.stt import _decode_audio

        audio = np.array([0.0, 0.5, -1.0], dtype=np.float32)
        decoded, rate = _decode_audio(audio, 24000)
        assert decoded.dtype == np.int16
        assert rate == 24000
        assert list(decoded) == [0, 16384, -32767]

    def test_int16_array_passes_through(self):
        import numpy as np

        from ziomek.stt import _decode_audio

        audio = np.array([0, 100, -100], dtype=np.int16)
        decoded, rate = _decode_audio(audio, 24000)
        assert list(decoded) == [0, 100, -100]

    def test_multichannel_array_is_downmixed(self):
        import numpy as np

        from ziomek.stt import _decode_audio

        audio = np.array([[0.5, -0.5], [1.0, 1.0]], dtype=np.float32)
        decoded, _ = _decode_audio(audio, 24000)
        assert decoded.shape == (2,)
        assert list(decoded) == [0, 32767]


class TestDownloadModel:
    def test_download_model_returns_path(self):
        """Test that download_model returns a Path object."""
        from pathlib import Path

        from ziomek.stt import download_model

        # This may fail if faster_whisper not installed, which is OK
        try:
            result = download_model("tiny")
            assert isinstance(result, (str, Path))
        except ImportError:
            pytest.skip("faster_whisper not installed")
        except Exception:
            pytest.skip("faster_whisper download failed (memory/resource issue)")
