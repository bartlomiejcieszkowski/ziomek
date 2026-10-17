"""Tests for TTS benchmark module."""

import pytest
import csv
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache


class TestBenchmarkMock:
    """Tests for TTS benchmark module using mocked model."""

    def test_benchmark_imports(self):
        """Benchmark module imports successfully."""
        from ziomek.tts.benchmark import SAMPLE_TEXTS, _run_benchmark, _print_summary

        assert len(SAMPLE_TEXTS) >= 3
        assert callable(_run_benchmark)
        assert callable(_print_summary)

    def test_benchmark_csv_output(self):
        """Benchmark produces valid CSV output with mocked model."""
        from ziomek.tts.benchmark import main

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_benchmark.csv"
            import sys

            # Mock sys.argv to avoid argparse errors
            sys.argv = [
                "benchmark",
                "--voices", "cosette",
                "--iterations", "1",
                "--output", str(csv_path),
                "--log-level", "ERROR",
            ]

            # Create a mock TTSModelWrapper with a ready model
            mock_model = MagicMock()
            mock_model.ready = True
            mock_model.sample_rate = 24000
            # Return a real numpy array (short sine wave)
            mock_audio_np = np.sin(np.linspace(0, 10, 24000)).astype(np.float32)

            def generate_with_delay(voice_state, text):
                time.sleep(0.01)  # Simulate 10ms generation time
                return mock_audio_np

            mock_model.generate_audio.side_effect = generate_with_delay

            with patch("ziomek.tts.benchmark.TTSModelWrapper", return_value=mock_model):
                try:
                    main()
                except SystemExit:
                    pass  # argparse may exit

            # Check CSV was created with headers
            assert csv_path.exists()
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                # CSV should have headers and rows
                assert reader.fieldnames is not None
                assert "voice" in reader.fieldnames
                assert "gen_time_ms" in reader.fieldnames
                assert len(rows) == 3  # 3 sample texts × 1 iteration

    def test_benchmark_long_text(self):
        """Benchmark handles longer paragraphs correctly."""
        from ziomek.tts.benchmark import _run_benchmark

        mock_model = MagicMock()
        mock_model.ready = True
        mock_model.sample_rate = 24000
        # Return a real numpy array (longer sine wave for longer text)
        mock_audio_np = np.sin(np.linspace(0, 10, 72000)).astype(np.float32)
        mock_model.generate_audio.return_value = mock_audio_np

        voice_cache = MagicMock()
        voice_cache.load_voice.return_value = {"prompt": "cosette"}

        long_text = (
            "The concept of artificial intelligence has evolved dramatically over the past "
            "decade. From simple rule-based systems to sophisticated deep learning models, "
            "AI has transformed industries ranging from healthcare to finance. Machine learning "
            "algorithms can now process vast amounts of data, recognize patterns in images and "
            "speech, and even generate creative content. The integration of natural language "
            "processing has made human-computer interaction more intuitive than ever before. "
            "As these technologies continue to advance, the potential for AI to augment human "
            "capabilities and solve complex global challenges becomes increasingly apparent."
        )

        results = _run_benchmark(mock_model, voice_cache, "cosette", [long_text], 2, output_dir=None)

        assert len(results) == 2  # 2 iterations
        for r in results:
            assert r["voice"] == "cosette"
            assert r["duration_s"] > 0  # Should have audio duration (72000 / 24000 = 3s)
            assert r["gen_time_ms"] >= 0  # Should have generation time
            assert r["rms"] > 0  # Should have non-zero RMS
            assert r["peak"] > 0  # Should have non-zero peak

    def test_benchmark_print_summary(self):
        """Benchmark summary prints correctly."""
        from ziomek.tts.benchmark import _print_summary

        results = [
            {
                "voice": "cosette",
                "text": "Hello",
                "iteration": 1,
                "duration_s": 1.0,
                "gen_time_ms": 100.0,
                "rms": 0.5,
                "peak": 1.0,
                "sample_rate": 24000,
            },
        ]
        # Should not raise
        _print_summary(results)


class TestBenchmarkReal:
    """Tests for TTS benchmark module using real TTS model."""

    def test_benchmark_real_generation(self):
        """Benchmark generates actual WAV from real TTS model."""
        from ziomek.tts.benchmark import _run_benchmark

        model = TTSModelWrapper()
        assert not model.ready, "Model should start unloaded"

        # Load the model
        model.load()
        assert model.ready, "Model should be ready after load()"

        voice_cache = VoiceStateCache(model)

        # Benchmark a short text
        results = _run_benchmark(model, voice_cache, "cosette", ["Hello world"], 1, output_dir=None)

        assert len(results) == 1
        r = results[0]
        assert r["voice"] == "cosette"
        assert r["duration_s"] > 0  # Real audio has duration
        assert r["gen_time_ms"] > 0  # Real generation takes time
        assert r["rms"] > 0  # Real audio has non-zero RMS
        assert r["peak"] > 0  # Real audio has non-zero peak
        assert r["sample_rate"] == 24000

    def test_benchmark_wav_output(self):
        """Benchmark saves WAV files when output_dir is specified."""
        from ziomek.tts.benchmark import _run_benchmark

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "wav"
            output_dir.mkdir()

            model = TTSModelWrapper()
            model.load()
            voice_cache = VoiceStateCache(model)

            results = _run_benchmark(
                model, voice_cache, "cosette",
                ["Hello world"], 1,
                output_dir=str(output_dir),
            )

            assert len(results) == 1
            # Check WAV file was created
            wav_files = list(output_dir.glob("*.wav"))
            assert len(wav_files) == 1
            assert wav_files[0].name.startswith("cosette")
            assert wav_files[0].name.endswith(".wav")
            # Verify file is non-empty
            assert wav_files[0].stat().st_size > 0
