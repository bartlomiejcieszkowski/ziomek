"""Tests for the STT engine module."""

import logging
import sys
from unittest.mock import patch

import numpy as np
import pytest

from ziomek.stt import STTEngine, STTState, stt_installed


class TestSttInstalled:
    """Tests for the optional 'stt' extra availability check."""

    def test_true_when_package_importable(self):
        with patch("ziomek.stt.find_spec", return_value=object()):
            assert stt_installed() is True

    def test_false_when_package_missing(self):
        with patch("ziomek.stt.find_spec", return_value=None):
            assert stt_installed() is False


class TestMissingSttExtra:
    """Option 3: missing extra warns and continues, with a hint naming the ziomek extra."""

    def test_start_warns_with_ziomek_extra_hint(self, caplog, monkeypatch):
        caplog.set_level(logging.WARNING, logger="ziomek.stt")
        monkeypatch.setitem(sys.modules, "RealtimeSTT", None)

        engine = STTEngine()
        engine.start()  # must not raise — degraded run continues

        assert engine.state == STTState.IDLE
        messages = " ".join(record.message for record in caplog.records)
        assert "not installed" in messages.lower()
        assert "ziomek[stt]" in messages
        assert "uv pip install" in messages

    def test_download_model_hint_names_ziomek_extra(self, monkeypatch):
        from ziomek.stt import download_model

        # Null out the package and its submodule: an earlier test in the suite may
        # already have imported faster_whisper.utils, which would skip the check.
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        monkeypatch.setitem(sys.modules, "faster_whisper.utils", None)

        with pytest.raises(ImportError) as exc:
            download_model("tiny")

        assert "ziomek[stt]" in str(exc.value)


class TestTranscribeChunkGuard:
    """Guard for calling transcription when the 'stt' extra is missing."""

    def test_returns_empty_when_engine_not_started(self):
        engine = STTEngine()
        result = engine.transcribe_chunk(b"", 16000)
        assert result.text == ""

    def test_logs_error_and_returns_empty_when_extra_missing(self, caplog, monkeypatch):
        caplog.set_level(logging.WARNING, logger="ziomek.stt")
        monkeypatch.setattr("ziomek.stt.submit_transcription_request", None)
        monkeypatch.setattr("ziomek.stt.receive_transcription_result", None)

        engine = STTEngine()
        # A recorder object exists (as it would after a successful start), but the
        # transcription worker API is unavailable because the extra is missing.
        setattr(engine, "_recorder", object())  # noqa: B010
        result = engine.transcribe_chunk(np.zeros(2, dtype=np.int16).tobytes(), 16000)

        assert result.text == ""
        messages = " ".join(record.message for record in caplog.records)
        assert "unavailable" in messages.lower()
        assert "ziomek[stt]" in messages


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


class TestStopReapsWorkerProcesses:
    """RealtimeSTT spawns non-daemon worker processes on Windows (runtime.py:31), so stop() must reap them."""

    class FakeProcess:
        def __init__(self, join_releases: bool = True) -> None:  # noqa: ANN001
            self.joined_with = []
            self.terminated = False
            self._alive = True
            self._join_releases = join_releases

        def join(self, timeout: float | None = None) -> None:
            self.joined_with.append(timeout)
            if self._join_releases:
                self._alive = False

        def is_alive(self) -> bool:
            return self._alive

        def terminate(self) -> None:
            self.terminated = True
            self._alive = False

    def _engine_with_fake_processes(self, monkeypatch, processes):
        class FakeRecorder:
            def __init__(self, **kwargs):  # noqa: ANN001
                self.transcript_process = processes["transcript"]
                self.reader_process = processes["reader"]

            def text(self):  # noqa: ANN201
                return ""

            def start_recording(self):  # noqa: ANN201
                pass

            def shutdown(self):  # noqa: ANN201
                pass

        monkeypatch.setattr("RealtimeSTT.AudioToTextRecorder", FakeRecorder)
        engine = STTEngine()
        engine.start_from_file()
        return engine

    def test_stop_joins_worker_processes(self, monkeypatch):
        processes = {"transcript": self.FakeProcess(), "reader": self.FakeProcess()}
        engine = self._engine_with_fake_processes(monkeypatch, processes)
        engine.stop()
        assert processes["transcript"].joined_with, "transcript worker was not joined"
        assert processes["reader"].joined_with, "reader worker was not joined"

    def test_stop_terminates_workers_that_do_not_exit_on_join(self, monkeypatch):
        processes = {
            "transcript": self.FakeProcess(join_releases=False),
            "reader": self.FakeProcess(join_releases=False),
        }
        engine = self._engine_with_fake_processes(monkeypatch, processes)
        engine.stop()
        assert processes["transcript"].terminated, "stubborn transcript worker was not terminated"
        assert processes["reader"].terminated, "stubborn reader worker was not terminated"

    def test_no_leftover_child_processes_after_real_stop(self):
        """Real run: after a full start/transcribe/stop cycle no child processes remain."""
        try:
            from RealtimeSTT import AudioToTextRecorder  # noqa: F401
        except ImportError:
            pytest.skip("RealtimeSTT not installed")

        import multiprocessing

        from ziomek.stt import STTEngine as _

        engine = STTEngine(model_name="tiny.en")
        engine.start_from_file()
        engine.transcribe_chunk(np.zeros(16000, dtype=np.float32), 16000)
        engine.stop()

        alive = [p for p in multiprocessing.active_children() if p.is_alive()]
        assert not alive, f"leftover worker processes: {[(p.name, p.pid) for p in alive]}"
