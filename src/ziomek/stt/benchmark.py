"""ziomek STT quality benchmark — transcription accuracy across engines/models.

Generates test audio from TTS, transcribes with different STT engines/models,
and measures quality using Levenshtein ratio and WER.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np  # type: ignore[import-untyped]
import scipy.io.wavfile as wavfile  # type: ignore[import-untyped]

from ziomek.stt import STTEngine, STTResult, STTState

logger = logging.getLogger(__name__)

# ── Test text samples ───────────────────────────────────────────────────────

SAMPLE_TEXTS = [
    ("simple", "Hello, how are you today?"),
    ("numbers", "The current time is 14:30 and the temperature is 22 degrees."),
    ("names", "My name is John Smith and I live in New York City."),
    ("technical", "The API endpoint returns a JSON response with a status code of 200."),
    ("complex", "Despite the heavy rain, the team managed to complete the project on time and deliver a high quality product."),
    ("long", "The quick brown fox jumps over the lazy dog. This sentence contains every letter of the English alphabet and is commonly used for testing purposes. It has been a staple of typography and font testing for over a century."),
]

DEFAULT_MODELS = ["tiny", "tiny.en", "base", "base.en", "small", "small.en"]

# ── Metrics ─────────────────────────────────────────────────────────────────

def levenshtein_ratio(s1: str, s2: str) -> float:
    """Character-level Levenshtein similarity ratio (0.0–1.0)."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    len1, len2 = len(s1), len(s2)
    # Full DP matrix
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return 1.0 - dp[len1][len2] / max(len1, len2)


def word_error_rate(s1: str, s2: str) -> float:
    """Word-level Word Error Rate (0.0 = perfect, 1.0 = completely wrong)."""
    if not s1 and not s2:
        return 0.0
    if not s1 or not s2:
        return 1.0
    words1 = s1.lower().split()
    words2 = s2.lower().split()
    if not words1 and not words2:
        return 0.0
    # Simple edit distance on word lists
    m, n = len(words1), len(words2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if words1[i - 1] == words2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n] / max(m, n)


# ── Benchmark runner ────────────────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    """Single benchmark run result."""
    engine: str
    model: str
    category: str
    original_text: str
    transcribed_text: str
    levenshtein: float
    wer: float
    gen_time_ms: float = 0.0
    transcribe_time_ms: float = 0.0
    duration_s: float = 0.0


def _run_single(
    engine: STTEngine,
    text: str,
    wav_path: Path,
    sample_rate: int = 24000,
    voice: str = "cosette",
) -> BenchmarkResult:
    """Generate WAV, transcribe, calculate metrics."""
    from ziomek.tts.engine import TTSModelWrapper
    from ziomek.tts.voice import VoiceStateCache

    # Generate audio from TTS
    model = TTSModelWrapper()
    model.load()
    cache = VoiceStateCache(model)
    voice_state = cache.load_voice(voice)
    start = time.time()
    audio_tensor = model.generate_audio(voice_state, text)
    gen_time = (time.time() - start) * 1000

    # Convert tensor to WAV
    audio_np = audio_tensor.detach().cpu().numpy()
    if audio_np.dtype == np.float32:
        audio_np = (audio_np * 32767).astype(np.int16)
    wavfile.write(str(wav_path), sample_rate, audio_np)

    # Transcribe
    engine.start()
    engine.start_recording()

    # Feed audio to STT engine
    audio_bytes = wav_path.read_bytes()
    result = engine.transcribe_chunk(audio_bytes, sample_rate)
    transcribe_time = time.time() - start

    engine.stop_recording()
    engine.stop()

    return BenchmarkResult(
        engine=engine._engine_name,
        model=engine._model_name,
        category="",  # filled by caller
        original_text=text,
        transcribed_text=result.text,
        levenshtein=levenshtein_ratio(text, result.text),
        wer=word_error_rate(text, result.text),
        gen_time_ms=gen_time,
        transcribe_time_ms=transcribe_time * 1000,
        duration_s=len(audio_np) / sample_rate,
    )


def run_benchmark(
    engines: list[str] | None = None,
    models: list[str] | None = None,
    categories: list[tuple[str, str]] | None = None,
    iterations: int = 1,
    output_dir: str | None = None,
    log_level: str = "WARNING",
) -> list[BenchmarkResult]:
    """Run STT quality benchmark.

    Args:
        engines: List of engine names (default: ["faster_whisper"]).
        models: List of model names (default: DEFAULT_MODELS).
        categories: List of (name, text) pairs (default: SAMPLE_TEXTS).
        iterations: Number of runs per config.
        output_dir: Directory for CSV/JSON output.
        log_level: Logging level.

    Returns:
        List of BenchmarkResult objects.
    """
    if engines is None:
        engines = ["faster_whisper"]
    if models is None:
        models = DEFAULT_MODELS
    if categories is None:
        categories = SAMPLE_TEXTS

    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.WARNING))

    results: list[BenchmarkResult] = []
    total = len(engines) * len(models) * len(categories) * iterations
    count = 0

    for engine_name in engines:
        for model_name in models:
            for cat_name, text in categories:
                for _ in range(iterations):
                    count += 1
                    logger.info(
                        "Running %d/%d: engine=%s model=%s category=%s",
                        count, total, engine_name, model_name, cat_name,
                    )

                    # Create engine with config
                    engine = STTEngine(
                        engine_name=engine_name,
                        model_name=model_name,
                    )

                    # Generate WAV in temp dir
                    tmp_dir = Path(__file__).parent.parent.parent / "tmp_bench"
                    tmp_dir.mkdir(exist_ok=True)
                    wav_path = tmp_dir / f"{engine_name}_{model_name}_{cat_name}_{count}.wav"

                    try:
                        result = _run_single(engine, text, wav_path)
                        result.category = cat_name
                        results.append(result)
                    except Exception:
                        logger.exception(
                            "Failed to benchmark engine=%s model=%s category=%s",
                            engine_name, model_name, cat_name,
                        )
                    finally:
                        engine.shutdown()

    # Write output
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # CSV
        csv_path = output_path / "benchmark_results.csv"
        try:
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "engine", "model", "category", "original_text",
                    "transcribed_text", "levenshtein", "wer",
                    "gen_time_ms", "transcribe_time_ms", "duration_s",
                ])
                writer.writeheader()
                for r in results:
                    writer.writerow(asdict(r))
        except OSError:
            logger.exception("Failed to write CSV output")

        # JSON summary
        json_path = output_path / "benchmark_summary.json"
        try:
            summary = {
                "total_runs": len(results),
                "engines": engines,
                "models": models,
                "categories": [c[0] for c in categories],
                "results": [asdict(r) for r in results],
            }
            with open(json_path, "w") as f:
                json.dump(summary, f, indent=2)
        except OSError:
            logger.exception("Failed to write JSON summary")

    return results


def print_summary(results: list[BenchmarkResult]) -> None:
    """Print a formatted summary table."""
    print("\n" + "=" * 80)
    print("STT Quality Benchmark Results")
    print("=" * 80)

    # Group by engine+model
    groups: dict[str, list[BenchmarkResult]] = {}
    for r in results:
        key = f"{r.engine}/{r.model}"
        groups.setdefault(key, []).append(r)

    for key, group in sorted(groups.items()):
        avg_lev = np.mean([r.levenshtein for r in group])
        avg_wer = np.mean([r.wer for r in group])
        avg_gen = np.mean([r.gen_time_ms for r in group])
        avg_trans = np.mean([r.transcribe_time_ms for r in group])

        print(f"\n{key} (avg over {len(group)} runs):")
        print(f"  Levenshtein: {avg_lev:.4f}  |  WER: {avg_wer:.4f}")
        print(f"  Gen time: {avg_gen:.1f}ms  |  Transcribe time: {avg_trans:.1f}ms")

        # Per-category
        for cat in sorted(set(r.category for r in group)):
            cat_results = [r for r in group if r.category == cat]
            cat_lev = np.mean([r.levenshtein for r in cat_results])
            cat_wer = np.mean([r.wer for r in cat_results])
            print(f"    {cat}: lev={cat_lev:.4f} wer={cat_wer:.4f}")

    print("\n" + "=" * 80)


def main() -> list[BenchmarkResult]:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="STT Quality Benchmark")
    parser.add_argument(
        "--engines", nargs="+", default=None,
        help="STT engines to test (default: faster_whisper)",
    )
    parser.add_argument(
        "--models", nargs="+", default=None,
        help=f"STT models to test (default: {DEFAULT_MODELS})",
    )
    parser.add_argument(
        "--categories", nargs="+", default=None,
        help="Category names to test (default: all)",
    )
    parser.add_argument(
        "--iterations", type=int, default=1,
        help="Number of runs per config (default: 1)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Directory for CSV/JSON output",
    )
    parser.add_argument(
        "--log-level", type=str, default="WARNING",
        help="Logging level (default: WARNING)",
    )

    args = parser.parse_args()

    # Parse categories
    categories = SAMPLE_TEXTS
    if args.categories:
        categories = [(n, t) for n, t in SAMPLE_TEXTS if n in args.categories]

    results = run_benchmark(
        engines=args.engines,
        models=args.models,
        categories=categories,
        iterations=args.iterations,
        output_dir=args.output_dir,
        log_level=args.log_level,
    )

    print_summary(results)
    return results


if __name__ == "__main__":
    main()
