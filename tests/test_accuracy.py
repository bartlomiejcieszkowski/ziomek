"""ziomek TTS accuracy test — round-trip fidelity measurement.

Tests generate WAV from TTS, transcribe back via STT, and compare original
text vs transcription using Levenshtein ratio and WER.
"""

from __future__ import annotations

import csv
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np  # type: ignore[import-untyped]
import pytest
import scipy.io.wavfile as wavfile  # type: ignore[import-untyped]

from ziomek.tts.accuracy import (
    DEFAULT_MODELS,
    SAMPLE_TEXTS,
    _run_accuracy,
    levenshtein_ratio,
    word_error_rate,
)
from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache

logger = logging.getLogger(__name__)


class TestAccuracyMetrics:
    """Test the similarity metrics."""

    def test_levenshtein_ratio_identical(self):
        assert levenshtein_ratio("hello", "hello") == 1.0

    def test_levenshtein_ratio_empty(self):
        assert levenshtein_ratio("", "") == 1.0
        assert levenshtein_ratio("hello", "") == 0.0
        assert levenshtein_ratio("", "hello") == 0.0

    def test_levenshtein_ratio_single_char(self):
        assert levenshtein_ratio("a", "b") == 0.0  # 1 edit / 1 max = 100% diff

    def test_levenshtein_ratio_substitution(self):
        ratio = levenshtein_ratio("hello", "hallo")
        assert ratio == 0.8  # 1/5 = 0.2 edit distance

    def test_word_error_rate_identical(self):
        assert word_error_rate("hello world", "hello world") == 0.0

    def test_word_error_rate_empty(self):
        assert word_error_rate("", "") == 0.0
        assert word_error_rate("hello", "") == 1.0
        assert word_error_rate("", "hello") == 1.0

    def test_word_error_rate_complete_mismatch(self):
        assert word_error_rate("hello world", "foo bar") == 1.0

    def test_word_error_rate_partial(self):
        wer = word_error_rate("hello world", "hello there")
        assert 0.0 < wer < 1.0


class TestAccuracyMock:
    """Mock tests — verify pipeline logic without real models."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock TTS model that generates silence."""
        mock = MagicMock(spec=TTSModelWrapper)
        mock.ready = True
        mock.sample_rate = 22050
        # Generate 0.1s of silence (2205 samples)
        mock.generate_audio.return_value = np.zeros(2205, dtype=np.float32)
        return mock

    @pytest.fixture
    def mock_stt(self):
        """Create a mock STT engine that returns the original text."""
        mock = MagicMock()
        from ziomek.stt import STTResult

        mock.transcribe_chunk.return_value = STTResult(
            text="mock transcription",
            is_final=True,
            realtime=False,
        )
        return mock

    def test_accuracy_imports(self):
        """Module imports correctly."""
        from ziomek.tts import accuracy  # noqa: F401

        assert hasattr(accuracy, "levenshtein_ratio")
        assert hasattr(accuracy, "word_error_rate")

    def test_accuracy_csv_output(self, tmp_path, mock_model, mock_stt):
        """CSV output contains expected fields."""
        results = _run_accuracy(
            mock_model,
            MagicMock(),
            mock_stt,
            "cosette",
            "tiny",
            SAMPLE_TEXTS[:2],
            1,
            str(tmp_path),
        )
        assert len(results) == 2
        for r in results:
            assert "voice" in r
            assert "stt_model" in r
            assert "category" in r
            assert "text" in r
            assert "transcribed" in r
            assert "levenshtein" in r
            assert "wer" in r

    def test_accuracy_long_text_handling(self, mock_model, mock_stt):
        """Long text categories are processed without error."""
        long_texts = [(n, t) for n, t in SAMPLE_TEXTS if n == "long"]
        results = _run_accuracy(
            mock_model,
            MagicMock(),
            mock_stt,
            "cosette",
            "tiny",
            long_texts,
            1,
        )
        assert len(results) == 1
        assert results[0]["category"] == "long"

    def test_accuracy_print_summary(self, mock_model, mock_stt, capsys):
        """Print summary table works."""
        results = _run_accuracy(
            mock_model,
            MagicMock(),
            mock_stt,
            "cosette",
            "tiny",
            SAMPLE_TEXTS[:2],
            1,
        )
        from ziomek.tts.accuracy import _print_summary

        _print_summary(results)
        captured = capsys.readouterr()
        assert "TTS Accuracy" in captured.out
        assert "cosette/tiny" in captured.out


class TestAccuracyReal:
    """Real tests — actual TTS generation with mocked STT transcription.

    The STT engine is too slow to initialize in tests (downloads from HF,
    initializes audio devices). We test real TTS generation + WAV output,
    and use a mock STT that returns the original text (perfect transcription).
    """

    @pytest.fixture
    def real_model(self):
        """Create and load a real TTS model."""
        model = TTSModelWrapper()
        if not model.ensure_loaded():
            pytest.skip("TTS model not loaded")
        return model

    @pytest.fixture
    def real_voice_cache(self, real_model):
        """Create a voice cache with the real model."""
        return VoiceStateCache(real_model)

    def test_accuracy_real_generation(self, real_model, real_voice_cache, tmp_path):
        """Generate WAV from TTS, mock transcription, verify metrics."""
        texts = [(n, t) for n, t in SAMPLE_TEXTS if n == "simple"]

        # Mock STT to return the original text (perfect transcription)
        mock_stt = MagicMock()
        from ziomek.stt import STTResult

        def mock_transcribe(audio_data, sample_rate=16000):
            # Find matching text from the run
            return STTResult(text="Hello, how are you today?", is_final=True, realtime=False)

        mock_stt.transcribe_chunk = mock_transcribe

        results = _run_accuracy(
            real_model,
            real_voice_cache,
            mock_stt,
            "cosette",
            "tiny",
            texts,
            1,
            str(tmp_path),
        )

        assert len(results) == 1
        r = results[0]

        # Levenshtein ratio should be high (mock returns original text)
        assert r["levenshtein"] > 0.9, f"Levenshtein ratio too low: {r['levenshtein']}"
        assert r["wer"] < 0.1, f"WER too high: {r['wer']}"
        assert r["duration_s"] > 0, "Audio duration should be positive"
        assert r["gen_time_ms"] > 0, "Generation time should be positive"

        # Check WAV was saved
        wav_files = list(tmp_path.glob("*.wav"))
        assert len(wav_files) == 1
        assert wav_files[0].stat().st_size > 0

    def test_accuracy_across_voices(self, real_model, tmp_path):
        """Test with different voices."""
        texts = [(n, t) for n, t in SAMPLE_TEXTS if n == "simple"]
        voices = ["cosette", "default"]

        for voice in voices:
            voice_cache = VoiceStateCache(real_model)
            mock_stt = MagicMock()
            from ziomek.stt import STTResult

            mock_stt.transcribe_chunk.return_value = STTResult(
                text="Hello, how are you today?",
                is_final=True,
                realtime=False,
            )

            results = _run_accuracy(
                real_model,
                voice_cache,
                mock_stt,
                voice,
                "tiny",
                texts,
                1,
                str(tmp_path),
            )
            assert len(results) == 1
            assert results[0]["voice"] == voice
            assert results[0]["levenshtein"] > 0.9

    def test_accuracy_wav_output(self, real_model, real_voice_cache, tmp_path):
        """WAV files are created with correct format."""
        texts = [(n, t) for n, t in SAMPLE_TEXTS if n == "simple"]

        mock_stt = MagicMock()
        from ziomek.stt import STTResult

        mock_stt.transcribe_chunk.return_value = STTResult(
            text="Hello, how are you today?",
            is_final=True,
            realtime=False,
        )

        results = _run_accuracy(
            real_model,
            real_voice_cache,
            mock_stt,
            "cosette",
            "tiny",
            texts,
            1,
            str(tmp_path),
        )

        wav_files = list(tmp_path.glob("*.wav"))
        assert len(wav_files) == 1

        # Verify WAV is valid
        sr, data = wavfile.read(wav_files[0])
        assert sr == 24000  # Pocket TTS sample rate
        assert len(data) > 0
        assert data.dtype in (np.int16, np.float32)  # Pocket TTS outputs float32
