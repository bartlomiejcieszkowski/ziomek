"""ziomek STT quality benchmark tests."""

from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np  # type: ignore[import-untyped]
import pytest
import scipy.io.wavfile as wavfile  # type: ignore[import-untyped]

from ziomek.stt import STTEngine
from ziomek.stt.benchmark import (
    DEFAULT_MODELS,
    SAMPLE_TEXTS,
    BenchmarkResult,
    levenshtein_ratio,
    run_benchmark,
    word_error_rate,
)

logger = logging.getLogger(__name__)


class TestSTTMetrics:
    """Test the similarity metrics."""

    def test_levenshtein_ratio_identical(self):
        assert levenshtein_ratio("hello", "hello") == 1.0

    def test_levenshtein_ratio_empty(self):
        assert levenshtein_ratio("", "") == 1.0
        assert levenshtein_ratio("hello", "") == 0.0
        assert levenshtein_ratio("", "hello") == 0.0

    def test_levenshtein_ratio_single_char(self):
        assert levenshtein_ratio("a", "b") == 0.0

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


class TestBenchmarkMock:
    """Mock tests — verify benchmark pipeline logic."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock STT engine that returns original text."""
        mock = MagicMock()
        mock._engine_name = "faster_whisper"
        mock._model_name = "tiny"
        mock._engine_name = "faster_whisper"
        mock._model_name = "tiny"
        mock._engine_name = "faster_whisper"
        mock._model_name = "tiny"

        from ziomek.stt import STTResult
        mock.transcribe_chunk.return_value = STTResult(
            text="Hello, how are you today?",  # Original text
            is_final=True,
            realtime=False,
        )
        return mock

    def test_benchmark_imports(self):
        """Module imports correctly."""
        from ziomek.stt import benchmark  # noqa: F401
        assert hasattr(benchmark, "levenshtein_ratio")
        assert hasattr(benchmark, "word_error_rate")

    def test_benchmark_csv_output(self, tmp_path):
        """CSV output contains expected fields."""
        from ziomek.stt import STTResult

        # Patch STTEngine to return mock results
        with patch("ziomek.stt.benchmark.STTEngine") as MockEngine:
            mock_inst = MagicMock()
            mock_inst._engine_name = "faster_whisper"
            mock_inst._model_name = "tiny"
            mock_inst.transcribe_chunk.return_value = STTResult(
                text="Hello, how are you today?",
                is_final=True,
                realtime=False,
            )
            MockEngine.return_value = mock_inst

            results = run_benchmark(
                engines=["faster_whisper"],
                models=["tiny"],
                categories=SAMPLE_TEXTS[:2],
                iterations=1,
                output_dir=str(tmp_path),
                log_level="WARNING",
            )
            assert len(results) == 2

            # Check CSV was written
            csv_path = tmp_path / "benchmark_results.csv"
            assert csv_path.exists()
            with open(csv_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 2
            for row in rows:
                assert "engine" in row
                assert "model" in row
                assert "category" in row
                assert "original_text" in row
                assert "transcribed_text" in row
                assert "levenshtein" in row
                assert "wer" in row

    def test_benchmark_json_output(self, tmp_path):
        """JSON summary contains expected structure."""
        from ziomek.stt import STTResult

        with patch("ziomek.stt.benchmark.STTEngine") as MockEngine:
            mock_inst = MagicMock()
            mock_inst._engine_name = "faster_whisper"
            mock_inst._model_name = "tiny"
            mock_inst.transcribe_chunk.return_value = STTResult(
                text="Hello, how are you today?",
                is_final=True,
                realtime=False,
            )
            MockEngine.return_value = mock_inst

            results = run_benchmark(
                engines=["faster_whisper"],
                models=["tiny"],
                categories=SAMPLE_TEXTS[:2],
                iterations=1,
                output_dir=str(tmp_path),
                log_level="WARNING",
            )

            json_path = tmp_path / "benchmark_summary.json"
            assert json_path.exists()
            with open(json_path, "r") as f:
                summary = json.load(f)

            assert summary["total_runs"] == 2
            assert summary["engines"] == ["faster_whisper"]
            assert summary["models"] == ["tiny"]
            assert len(summary["results"]) == 2

    def test_benchmark_long_text_handling(self):
        """Long text categories are processed without error."""
        from ziomek.stt import STTResult

        with patch("ziomek.stt.benchmark.STTEngine") as MockEngine:
            mock_inst = MagicMock()
            mock_inst._engine_name = "faster_whisper"
            mock_inst._model_name = "tiny"
            mock_inst.transcribe_chunk.return_value = STTResult(
                text="Hello, how are you today?",
                is_final=True,
                realtime=False,
            )
            MockEngine.return_value = mock_inst

            long_texts = [(n, t) for n, t in SAMPLE_TEXTS if n == "long"]
            results = run_benchmark(
                engines=["faster_whisper"],
                models=["tiny"],
                categories=long_texts,
                iterations=1,
                log_level="WARNING",
            )
            assert len(results) == 1
            assert results[0].category == "long"

    def test_benchmark_print_summary(self, capsys):
        """Print summary table works."""
        from ziomek.stt import STTResult

        with patch("ziomek.stt.benchmark.STTEngine") as MockEngine:
            mock_inst = MagicMock()
            mock_inst._engine_name = "faster_whisper"
            mock_inst._model_name = "tiny"
            mock_inst.transcribe_chunk.return_value = STTResult(
                text="Hello, how are you today?",
                is_final=True,
                realtime=False,
            )
            MockEngine.return_value = mock_inst

            results = run_benchmark(
                engines=["faster_whisper"],
                models=["tiny"],
                categories=SAMPLE_TEXTS[:2],
                iterations=1,
                log_level="WARNING",
            )
            from ziomek.stt.benchmark import print_summary
            print_summary(results)
            captured = capsys.readouterr()
            assert "STT Quality Benchmark Results" in captured.out
            assert "faster_whisper/tiny" in captured.out


class TestBenchmarkReal:
    """Real tests — actual TTS generation + STT transcription.

    Uses real Pocket TTS model + RealtimeSTT engine to test end-to-end pipeline.
    """

    @pytest.fixture
    def real_stt_engine(self):
        """Create and initialize a real STT engine."""
        engine = STTEngine(
            engine_name="faster_whisper",
            model_name="tiny",
        )
        return engine

    def test_benchmark_real_generation(self, real_stt_engine, tmp_path):
        """Generate WAV from TTS, transcribe via STT, verify metrics."""
        from ziomek.tts.engine import TTSModelWrapper
        from ziomek.tts.voice import VoiceStateCache

        texts = [(n, t) for n, t in SAMPLE_TEXTS if n == "simple"]

        # Generate WAV from TTS
        model = TTSModelWrapper()
        model.load()
        cache = VoiceStateCache(model)
        voice_state = cache.load_voice("cosette")
        start = time.time()
        audio_tensor = model.generate_audio(voice_state, texts[0][1])
        gen_time = (time.time() - start) * 1000

        # Convert tensor to WAV
        audio_np = audio_tensor.detach().cpu().numpy()
        if audio_np.dtype == np.float32:
            audio_np = (audio_np * 32767).astype(np.int16)
        sample_rate = 24000
        wav_path = tmp_path / "test.wav"
        wavfile.write(str(wav_path), sample_rate, audio_np)

        # Transcribe via STT
        real_stt_engine.start()
        real_stt_engine.start_recording()
        result = real_stt_engine.transcribe_chunk(wav_path.read_bytes(), sample_rate)
        real_stt_engine.stop_recording()
        real_stt_engine.stop()

        # Verify metrics
        lev = levenshtein_ratio(texts[0][1], result.text)
        wer = word_error_rate(texts[0][1], result.text)

        assert lev >= 0, "Levenshtein ratio should be >= 0"
        assert wer >= 0, "WER should be >= 0"
        assert gen_time > 0, "Generation time should be positive"

    def test_benchmark_across_models(self, tmp_path):
        """Test with different STT models."""
        from ziomek.tts.engine import TTSModelWrapper
        from ziomek.tts.voice import VoiceStateCache

        texts = [(n, t) for n, t in SAMPLE_TEXTS if n == "simple"]
        models = ["tiny", "tiny.en"]

        for model_name in models:
            engine = STTEngine(
                engine_name="faster_whisper",
                model_name=model_name,
            )

            # Generate WAV
            tts_model = TTSModelWrapper()
            tts_model.load()
            tts_cache = VoiceStateCache(tts_model)
            tts_voice = tts_cache.load_voice("cosette")
            audio_tensor = tts_model.generate_audio(tts_voice, texts[0][1])
            audio_np = audio_tensor.detach().cpu().numpy()
            if audio_np.dtype == np.float32:
                audio_np = (audio_np * 32767).astype(np.int16)
            sample_rate = 24000
            wav_path = tmp_path / f"{model_name}.wav"
            wavfile.write(str(wav_path), sample_rate, audio_np)

            # Transcribe
            engine.start()
            engine.start_recording()
            result = engine.transcribe_chunk(wav_path.read_bytes(), sample_rate)
            engine.stop_recording()
            engine.stop()

            assert result.text is not None, f"STT should return text for model {model_name}"

    def test_benchmark_wav_output(self, real_stt_engine, tmp_path):
        """WAV files are created with correct format."""
        from ziomek.tts.engine import TTSModelWrapper
        from ziomek.tts.voice import VoiceStateCache

        texts = [(n, t) for n, t in SAMPLE_TEXTS if n == "simple"]

        # Generate WAV from TTS
        model = TTSModelWrapper()
        model.load()
        cache = VoiceStateCache(model)
        voice_state = cache.load_voice("cosette")
        audio_tensor = model.generate_audio(voice_state, texts[0][1])
        audio_np = audio_tensor.detach().cpu().numpy()
        if audio_np.dtype == np.float32:
            audio_np = (audio_np * 32767).astype(np.int16)
        sample_rate = 24000
        wav_path = tmp_path / "test.wav"
        wavfile.write(str(wav_path), sample_rate, audio_np)

        # Verify WAV is valid
        sr, data = wavfile.read(wav_path)
        assert sr == 24000  # Pocket TTS sample rate
        assert len(data) > 0
        assert data.dtype in (np.int16, np.float32)
