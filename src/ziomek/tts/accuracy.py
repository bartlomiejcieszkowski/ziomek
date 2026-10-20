#!/usr/bin/env python
"""ziomek TTS accuracy test — measure round-trip fidelity.

Generate WAV from TTS → transcribe back via STT → compare original text vs
transcription → measure fidelity using Levenshtein ratio and WER.

Usage:
    uv run python -m ziomek.tts.accuracy [--voices cosette default]
    uv run python -m ziomek.tts.accuracy --models tiny base --output report.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np  # type: ignore[import-untyped]
import scipy.io.wavfile as wavfile  # type: ignore[import-untyped]
import torch  # type: ignore[import-untyped]

from ziomek.tts.engine import TTSModelWrapper
from ziomek.tts.voice import VoiceStateCache

logger = logging.getLogger(__name__)

# Default text categories
SAMPLE_TEXTS: list[tuple[str, str]] = [
    ("simple", "Hello, how are you today?"),
    ("complex", "The quick brown fox jumps over the lazy dog."),
    ("names", "My name is Ziomek and I am a humanize AI project."),
    ("numbers", "The year is 2026 and the temperature is 23.5 degrees."),
    (
        "technical",
        "The API endpoint is /api/tts/synthesize with content type application/json.",
    ),
    (
        "long",
        "Ziomek is a humanize AI project that combines text-to-speech, "
        "speech-to-text, and avatar rendering into a single local-first "
        "application. It is designed to be fully offline and privacy-friendly.",
    ),
]

# Default STT models
DEFAULT_MODELS: list[str] = [
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
]


def levenshtein_ratio(s1: str, s2: str) -> float:
    """Calculate Levenshtein similarity ratio (0.0–1.0)."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Use dynamic programming for edit distance
    rows = len(s1) + 1
    cols = len(s2) + 1
    dp = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        dp[i][0] = i
    for j in range(cols):
        dp[0][j] = j

    for col in range(1, cols):
        for row in range(1, rows):
            if s1[row - 1] == s2[col - 1]:
                cost = 0
            else:
                cost = 1
            dp[row][col] = min(
                dp[row - 1][col] + 1,  # deletion
                dp[row][col - 1] + 1,  # insertion
                dp[row - 1][col - 1] + cost,  # substitution
            )

    edit_distance = dp[rows - 1][cols - 1]
    max_len = max(len(s1), len(s2))
    return 1.0 - (edit_distance / max_len)


def word_error_rate(s1: str, s2: str) -> float:
    """Calculate Word Error Rate (0.0 = perfect, 1.0 = completely wrong)."""
    words1 = s1.lower().split()
    words2 = s2.lower().split()

    if not words1 and not words2:
        return 0.0
    if not words1 or not words2:
        return 1.0

    # Use Levenshtein on word sequences
    rows = len(words1) + 1
    cols = len(words2) + 1
    dp = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        dp[i][0] = i
    for j in range(cols):
        dp[0][j] = j

    for col in range(1, cols):
        for row in range(1, rows):
            if words1[row - 1] == words2[col - 1]:
                cost = 0
            else:
                cost = 1
            dp[row][col] = min(
                dp[row - 1][col] + 1,
                dp[row][col - 1] + 1,
                dp[row - 1][col - 1] + cost,
            )

    edit_distance = dp[rows - 1][cols - 1]
    return edit_distance / len(words1)


def _run_accuracy(
    model: TTSModelWrapper,
    voice_cache: VoiceStateCache,
    stt_engine,
    voice: str,
    stt_model: str,
    categories: list[tuple[str, str]],
    iterations: int,
    output_dir: str | None = None,
) -> list[dict[str, Any]]:
    """Run accuracy test for a single voice and STT model across categories."""
    results: list[dict[str, Any]] = []

    for cat_name, text in categories:
        for i in range(iterations):
            voice_state = voice_cache.load_voice(voice)

            if not model.ready:
                logger.warning("Model not ready, skipping")
                continue

            # Generate WAV
            start = time.perf_counter()
            audio_tensor = model.generate_audio(voice_state, text)
            gen_time_ms = (time.perf_counter() - start) * 1000

            if isinstance(audio_tensor, torch.Tensor):
                audio_np = audio_tensor.detach().cpu().numpy()
            else:
                audio_np = np.array(audio_tensor)

            sample_rate = model.sample_rate
            duration = len(audio_np) / sample_rate if hasattr(audio_np, "__len__") else 0

            # Save WAV
            wav_path = None
            if output_dir:
                wav_path = Path(output_dir) / f"{voice}_{cat_name}_{stt_model}_{i + 1:02d}.wav"
                wavfile.write(wav_path, sample_rate, audio_np)

            # Transcribe back
            if len(audio_np) > 0:
                # Convert to bytes for STT
                audio_bytes = audio_np.astype(np.int16).tobytes()
                stt_result = stt_engine.transcribe_chunk(audio_bytes, sample_rate)
                transcribed = stt_result.text
            else:
                transcribed = ""

            # Calculate similarity
            lev_ratio = levenshtein_ratio(text, transcribed)
            wer = word_error_rate(text, transcribed)

            results.append(
                {
                    "voice": voice,
                    "stt_model": stt_model,
                    "category": cat_name,
                    "text": text,
                    "transcribed": transcribed,
                    "iteration": i + 1,
                    "duration_s": round(duration, 3),
                    "gen_time_ms": round(gen_time_ms, 1),
                    "levenshtein": round(lev_ratio, 4),
                    "wer": round(wer, 4),
                }
            )

            logger.info(
                "  voice=%s model=%s cat=%s lev=%.4f wer=%.4f gen=%.1fms",
                voice,
                stt_model,
                cat_name,
                lev_ratio,
                wer,
                gen_time_ms,
            )

    return results


def _print_summary(results: list[dict[str, Any]]) -> None:
    """Print a summary table to stdout."""
    print("\n" + "=" * 80)
    print("TTS Accuracy Round-Trip Summary")
    print("=" * 80)

    # Group by voice + model
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        key = f"{r['voice']}/{r['stt_model']}"
        groups.setdefault(key, []).append(r)

    for key in sorted(groups):
        group = groups[key]
        levs = [r["levenshtein"] for r in group]
        wers = [r["wer"] for r in group]
        cats = sorted(set(r["category"] for r in group))

        print(f"\n  {key}:")
        print(f"    Total generations: {len(group)}")

        for cat in cats:
            cat_results = [r for r in group if r["category"] == cat]
            cat_levs = [r["levenshtein"] for r in cat_results]
            cat_wers = [r["wer"] for r in cat_results]
            print(
                f"      {cat:12s}  lev={statistics.mean(cat_levs):.4f}  "
                f"wer={statistics.mean(cat_wers):.4f}  "
                f"({len(cat_results)} samples)"
            )

        print(f"      {'overall':12s}  lev={statistics.mean(levs):.4f}  wer={statistics.mean(wers):.4f}")

    print("\n" + "=" * 80)


def main(  # noqa: PLR0915 (complex function — benchmark runner)
    voices: list[str] | None = None,
    models: list[str] | None = None,
    categories: list[str] | None = None,
    iterations: int | None = None,
    output: str | None = None,
    output_dir: str | None = None,
    store: bool = False,
    store_dir: str = "benchmarks",
    log_level: str = "INFO",
) -> list[dict[str, Any]]:
    import sys

    # If called from CLI (no args provided), parse from command line
    if voices is None:
        parser = argparse.ArgumentParser(description="ziomek TTS accuracy test")
        parser.add_argument(
            "--voices",
            nargs="+",
            default=["cosette", "default"],
            help="Voices to test",
        )
        parser.add_argument(
            "--models",
            nargs="+",
            default=DEFAULT_MODELS,
            help="STT models to test (default: all)",
        )
        parser.add_argument(
            "--categories",
            nargs="+",
            default=["simple", "complex", "names", "numbers", "technical", "long"],
            help="Categories to test",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=1,
            help="Iterations per category per voice",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="CSV output file path",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default=None,
            help="Directory to save WAV files",
        )
        parser.add_argument(
            "--store",
            action="store_true",
            help="Save benchmark results to store.py",
        )
        parser.add_argument(
            "--store-dir",
            type=str,
            default="benchmarks",
            help="Benchmark store directory (default: benchmarks)",
        )
        parser.add_argument(
            "--log-level",
            default="INFO",
            help="Log level",
        )
        args = parser.parse_args()

        voices = args.voices
        models = args.models
        categories = args.categories
        iterations = args.iterations
        output = args.output
        output_dir = args.output_dir
        store = args.store
        store_dir = args.store_dir
        log_level = args.log_level
    else:
        # Use defaults for any None values
        if models is None:
            models = DEFAULT_MODELS
        if categories is None:
            categories = ["simple", "complex", "names", "numbers", "technical", "long"]
        if iterations is None:
            iterations = 1

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(message)s",
    )

    # Filter categories
    cat_names = set(categories)
    filtered_texts = [(n, t) for n, t in SAMPLE_TEXTS if n in cat_names]

    print(f"Voices: {', '.join(voices)}")
    print(f"STT models: {', '.join(models)}")
    print(f"Categories: {', '.join(categories)}")
    print(f"Iterations: {iterations}")
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        print(f"WAV output directory: {output_dir}")
    print()

    # Initialize model and STT engine
    model = TTSModelWrapper()
    voice_cache = VoiceStateCache(model)

    try:
        from ziomek.stt import STTEngine

        stt_engine = STTEngine()
        stt_engine.start()
    except Exception as e:
        logger.warning("STT engine failed to start: %s — running TTS-only mode", e)
        stt_engine = None

    all_results: list[dict[str, Any]] = []

    for voice in voices:
        for stt_model in models:
            if stt_engine:
                stt_engine.reconfigure("faster_whisper", stt_model)

            print(f"Testing voice={voice} model={stt_model}")
            try:
                results = _run_accuracy(
                    model,
                    voice_cache,
                    stt_engine,
                    voice,
                    stt_model,
                    filtered_texts,
                    iterations,
                    output_dir,
                )
                all_results.extend(results)
            except Exception as e:
                logger.warning(
                    "voice=%s model=%s failed: %s",
                    voice,
                    stt_model,
                    e,
                )

    if stt_engine:
        stt_engine.shutdown()

    _print_summary(all_results)

    # Write CSV
    csv_path = output or "tts_accuracy.csv"
    fieldnames = [
        "voice",
        "stt_model",
        "category",
        "text",
        "transcribed",
        "iteration",
        "duration_s",
        "gen_time_ms",
        "levenshtein",
        "wer",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nCSV report written to: {csv_path}")

    # Save to benchmark store
    if store:
        from ziomek.benchmark.store import create_run, save_run

        # Collect unique STT models and voices from results
        stt_models = list(set(r["stt_model"] for r in all_results))
        tts_voices = list(set(r["voice"] for r in all_results))

        run = create_run(
            results=[
                {
                    "model": r["stt_model"],
                    "category": r["category"],
                    "levenshtein": r["levenshtein"],
                    "wer": r["wer"],
                }
                for r in all_results
            ],
            stt_models=stt_models,
            tts_voices=tts_voices,
        )
        path = save_run(run, store_dir=store_dir)
        print(f"\nBenchmark result saved to: {path}")

    return all_results


if __name__ == "__main__":
    main()
