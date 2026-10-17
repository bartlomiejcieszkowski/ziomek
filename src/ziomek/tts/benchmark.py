#!/usr/bin/env python
"""ziomek TTS benchmark — compare generation speed and audio quality across voices.

Usage:
    uv run python -m ziomek.tts.benchmark [--voices cosette default] [--iterations 3]

Outputs a CSV report with: voice, text, duration, gen_time_ms, rms, peak, sample_rate
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np  # type: ignore[import-untyped]
import scipy.io.wavfile as wavfile  # type: ignore[import-untyped]
import torch  # type: ignore[import-untyped]

from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache

logger = logging.getLogger(__name__)

SAMPLE_TEXTS = [
    "Hello, how are you today?",
    "The quick brown fox jumps over the lazy dog.",
    "Ziomek is a humanize AI project.",
]


def _run_benchmark(
    model: TTSModelWrapper,
    voice_cache: VoiceStateCache,
    voice: str,
    texts: list[str],
    iterations: int,
    output_dir: str | None = None,
) -> list[dict[str, Any]]:
    """Run benchmark for a single voice across multiple texts and iterations."""
    results: list[dict[str, Any]] = []

    for text in texts:
        for i in range(iterations):
            voice_state = voice_cache.load_voice(voice)
            start = time.perf_counter()

            if not model.ready:
                logger.warning("Model not ready, skipping")
                continue

            audio_tensor = model.generate_audio(voice_state, text)
            if isinstance(audio_tensor, torch.Tensor):  # noqa: F821
                audio_np = audio_tensor.detach().cpu().numpy()
            else:
                audio_np = np.array(audio_tensor)

            elapsed_ms = (time.perf_counter() - start) * 1000
            sample_rate = model.sample_rate
            duration = len(audio_np) / sample_rate if hasattr(audio_np, "__len__") else 0

            # Audio quality metrics
            rms = float(np.sqrt(np.mean(audio_np.astype(float) ** 2))) if len(audio_np) > 0 else 0.0
            peak = float(np.max(np.abs(audio_np))) if len(audio_np) > 0 else 0.0

            results.append({
                "voice": voice,
                "text": text,
                "iteration": i + 1,
                "duration_s": round(duration, 3),
                "gen_time_ms": round(elapsed_ms, 1),
                "rms": round(rms, 4),
                "peak": round(peak, 4),
                "sample_rate": sample_rate,
            })

            # Optionally save WAV file
            if output_dir:
                wav_path = Path(output_dir) / f"{voice}_{text[:20].replace(' ', '_')}_{i+1:02d}.wav"
                wavfile.write(wav_path, sample_rate, audio_np)
                logger.info("  WAV saved to: %s", wav_path)

            logger.info(
                "  voice=%s text=%r iter=%d gen=%.1fms dur=%.3fs rms=%.4f peak=%.4f",
                voice, text[:30], i + 1, elapsed_ms, duration, rms, peak,
            )

    return results


def _print_summary(results: list[dict[str, Any]]) -> None:
    """Print a summary table to stdout."""
    print("\n" + "=" * 70)
    print("TTS Benchmark Summary")
    print("=" * 70)

    voices = sorted(set(r["voice"] for r in results))
    for voice in voices:
        voice_results = [r for r in results if r["voice"] == voice]
        gen_times = [r["gen_time_ms"] for r in voice_results]
        durations = [r["duration_s"] for r in voice_results]

        print(f"\n  {voice}:")
        print(f"    Generations:    {len(gen_times)}")
        print(f"    Avg gen time:   {statistics.mean(gen_times):.1f} ms")
        print(f"    Min gen time:   {min(gen_times):.1f} ms")
        print(f"    Max gen time:   {max(gen_times):.1f} ms")
        print(f"    Avg duration:   {statistics.mean(durations):.3f} s")
        print(f"    Speed factor:   {statistics.mean(durations) / statistics.mean(gen_times) * 1000:.2f}x real-time")

    print("\n" + "=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="ziomek TTS benchmark")
    parser.add_argument("--voices", nargs="+", default=["cosette", "default"], help="Voices to benchmark")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations per text per voice")
    parser.add_argument("--output", type=str, default=None, help="CSV output file path")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save WAV files (default: no WAV output)")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level, logging.INFO), format="%(message)s")

    # Initialize model
    model = TTSModelWrapper()
    voice_cache = VoiceStateCache(model)

    print(f"Benchmarking voices: {', '.join(args.voices)}")
    print(f"Iterations: {args.iterations} per text")
    print(f"Sample texts: {len(SAMPLE_TEXTS)}")
    if args.output_dir:
        print(f"WAV output directory: {args.output_dir}")
    print()

    all_results: list[dict[str, Any]] = []

    for voice in args.voices:
        print(f"\nBenchmarking voice: {voice}")
        try:
            results = _run_benchmark(model, voice_cache, voice, SAMPLE_TEXTS, args.iterations, args.output_dir)
            all_results.extend(results)
        except Exception as e:
            logger.warning("Voice %s benchmark failed: %s", voice, e)

    _print_summary(all_results)

    # Write CSV
    csv_path = args.output or "tts_benchmark.csv"
    fieldnames = ["voice", "text", "iteration", "duration_s", "gen_time_ms", "rms", "peak", "sample_rate"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nCSV report written to: {csv_path}")

    return all_results


if __name__ == "__main__":
    main()
