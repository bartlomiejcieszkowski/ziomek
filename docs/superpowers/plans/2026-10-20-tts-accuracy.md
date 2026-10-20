# TTS Accuracy Round-Trip Test

**Date:** 2026-10-20
**Status:** Draft

---

## Overview

Generate WAV from TTS → transcribe back via STT → compare original text vs transcription → measure fidelity.

## Design

### Text categories

| Category | Example | Purpose |
|----------|---------|---------|
| Simple | "Hello, how are you?" | Baseline fidelity |
| Complex | "The quick brown fox jumps over the lazy dog." | Common phrases |
| Names | "My name is Ziomek and I am a humanize AI project" | Proper nouns |
| Numbers | "The year is 2026 and the temperature is 23.5 degrees" | Digits/decimals |
| Technical | "The API endpoint is /api/tts/synthesize with content type application/json" | Technical terms |
| Long | Multi-sentence paragraph | Error accumulation |

### Voices

- Default voices from `ziomek.tts.voice` (cosette, default)
- Customizable via `--voices` flag
- Expandable as new voices are added

### STT Models

Default expandable list:
```
tiny, tiny.en, base, base.en, small, small.en
```

Customizable via `--models` flag.

### Similarity metrics

1. **Levenshtein ratio** (0.0–1.0): character-level edit distance normalized. Catches subtle errors.
2. **Word Error Rate (WER)**: word-level. More meaningful for practical use.

### Output

- **CLI tool**: `uv run python -m ziomek.tts.accuracy`
- **Test file**: `tests/test_accuracy.py` with mock + real tests
- **CSV report**: like the benchmark
- **Per-voice/model summary table**

### CLI interface

```bash
# Run with defaults (cosette voice, all models, all categories)
uv run python -m ziomek.tts.accuracy

# Custom voices
uv run python -m ziomek.tts.accuracy --voices cosette default

# Custom models
uv run python -m ziomek.tts.accuracy --models tiny base

# Save CSV
uv run python -m ziomek.tts.accuracy --output accuracy_report.csv

# Save WAV files for inspection
uv run python -m ziomek.tts.accuracy --output-dir accuracy_wavs/

# Specific categories only
uv run python -m ziomek.tts.accuracy --categories simple numbers
```

### File structure

```
src/ziomek/tts/accuracy.py       # CLI tool
tests/test_accuracy.py           # Tests (mock + real)
```

### Test structure

```python
class TestAccuracyMock:
    """Mock tests — verify pipeline logic without real models."""
    test_accuracy_imports
    test_accuracy_csv_output
    test_accuracy_long_text_handling
    test_accuracy_print_summary

class TestAccuracyReal:
    """Real tests — actual TTS → STT round-trip."""
    test_accuracy_real_generation        # Generate WAV, transcribe back, measure similarity
    test_accuracy_across_voices          # Test with different voices
    test_accuracy_across_models          # Test with different STT models
    test_accuracy_wav_output             # Verify WAV file creation
```

### Expected fidelity ranges

| Category | tiny | base | small |
|----------|------|------|-------|
| Simple | 0.90–1.00 | 0.95–1.00 | 0.95–1.00 |
| Complex | 0.85–0.95 | 0.90–0.98 | 0.92–0.99 |
| Names | 0.80–0.92 | 0.85–0.95 | 0.88–0.97 |
| Numbers | 0.85–0.95 | 0.90–0.98 | 0.92–0.99 |
| Technical | 0.75–0.88 | 0.82–0.93 | 0.85–0.95 |
| Long | 0.70–0.85 | 0.78–0.90 | 0.82–0.92 |

These are estimates — actual results will vary. The test reports but doesn't assert thresholds.

### Dependencies

- `nltk` — for WER calculation (`nltk.word_tokenize`)
- `jiwer` — for Levenshtein ratio (optional, can use `difflib` fallback)
- Or implement both metrics manually to avoid new dependencies

**Decision**: Implement both metrics manually to avoid new dependencies. Levenshtein is simple to implement. WER can use `difflib.SequenceMatcher` for word-level matching.

---

## Tasks

### Task 1: Create accuracy.py CLI tool

- Implement `ziomek.tts.accuracy` module
- Text categories list (configurable)
- Default voices from voice cache
- Default model list (expandable)
- Levenshtein ratio implementation
- WER implementation
- CSV report output
- WAV file output (--output-dir)
- Print summary table

### Task 2: Create tests/test_accuracy.py

- TestAccuracyMock: imports, CSV output, long text, print summary
- TestAccuracyReal: real generation, across voices, across models, WAV output
- Use pytest tmp_path for WAV files

### Task 3: Update README.md

- Add accuracy test section
- Usage examples

### Task 4: Update TODO.md

- Mark TTS accuracy test as done
