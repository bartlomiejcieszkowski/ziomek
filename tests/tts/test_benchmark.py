"""Tests for TTS benchmark module."""

import pytest
import csv
import tempfile
from pathlib import Path


class TestBenchmark:
    """Tests for TTS benchmark module."""

    def test_benchmark_imports(self):
        """Benchmark module imports successfully."""
        from ziomek.tts.benchmark import SAMPLE_TEXTS, _run_benchmark, _print_summary

        assert len(SAMPLE_TEXTS) >= 3
        assert callable(_run_benchmark)
        assert callable(_print_summary)

    def test_benchmark_csv_output(self):
        """Benchmark produces valid CSV output."""
        from ziomek.tts.benchmark import main

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_benchmark.csv"
            import sys
            from unittest.mock import patch

            # Mock sys.argv to avoid argparse errors
            sys.argv = [
                "benchmark",
                "--voices", "cosette",
                "--iterations", "1",
                "--output", str(csv_path),
                "--log-level", "ERROR",
            ]

            try:
                main()
            except SystemExit:
                pass  # argparse may exit

            # Check CSV was created with headers
            assert csv_path.exists()
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                # CSV should have headers
                assert reader.fieldnames is not None
                assert "voice" in reader.fieldnames
                assert "gen_time_ms" in reader.fieldnames
