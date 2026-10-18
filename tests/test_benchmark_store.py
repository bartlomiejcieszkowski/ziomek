"""Tests for src/ziomek/benchmark/store.py — versioned benchmark result history."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from ziomek.benchmark.store import (
    BenchmarkRun,
    create_run,
    diff_runs,
    list_runs,
    load_run,
    main,
    print_diff,
    save_run,
)

# ── helpers ─────────────────────────────────────────────────────────────────


def _make_result(model: str, category: str, levenshtein: float, wer: float) -> dict:
    return {
        "model": model,
        "category": category,
        "levenshtein": levenshtein,
        "wer": wer,
    }


def _make_run(results: list[dict], store_dir: str) -> BenchmarkRun:
    return create_run(
        results=results,
        stt_models=["tiny"],
        stt_engines=["faster_whisper"],
        tts_voices=["cosette"],
    )


# ── create_run ──────────────────────────────────────────────────────────────


class TestCreateRun:
    def test_creates_run_with_metadata(self):
        run = create_run(
            results=[_make_result("tiny", "simple", 0.95, 0.10)],
            stt_models=["tiny"],
            tts_voices=["cosette"],
        )
        assert isinstance(run, BenchmarkRun)
        assert run.run_id is not None
        assert run.timestamp is not None
        assert run.stt_models == ["tiny"]
        assert run.tts_voices == ["cosette"]
        assert len(run.results) == 1

    def test_run_has_library_version(self):
        run = create_run(
            results=[],
            stt_models=[],
            tts_voices=[],
        )
        assert run.pocket_tts_version is not None
        assert run.faster_whisper_version is not None

    def test_run_has_git_info(self):
        with patch("ziomek.benchmark.store._get_git_info", return_value=("abc123", "main")):
            run = create_run(results=[], stt_models=[], tts_voices=[])
            assert run.git_commit == "abc123"
            assert run.git_branch == "main"

    def test_run_has_python_platform(self):
        run = create_run(results=[], stt_models=[], tts_voices=[])
        assert run.python_version is not None
        assert run.platform is not None


# ── save_run / load_run ─────────────────────────────────────────────────────


class TestSaveLoad:
    def test_save_creates_file(self, tmp_path: Path):
        run = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        path = save_run(run, store_dir=str(tmp_path))
        assert path.exists()
        assert path.name == f"{run.run_id}.json"

    def test_save_writes_valid_json(self, tmp_path: Path):
        run = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        path = save_run(run, store_dir=str(tmp_path))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["run_id"] == run.run_id
        assert data["timestamp"] == run.timestamp
        assert data["stt_models"] == ["tiny"]

    def test_save_load_roundtrip(self, tmp_path: Path):
        run = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        save_run(run, store_dir=str(tmp_path))
        loaded = load_run(run.run_id, store_dir=str(tmp_path))
        assert loaded is not None
        assert loaded.run_id == run.run_id
        assert loaded.timestamp == run.timestamp
        assert len(loaded.results) == len(run.results)
        assert loaded.results[0]["model"] == run.results[0]["model"]
        assert loaded.results[0]["levenshtein"] == run.results[0]["levenshtein"]

    def test_save_returns_path(self, tmp_path: Path):
        run = _make_run([], str(tmp_path))
        path = save_run(run, store_dir=str(tmp_path))
        assert isinstance(path, Path)

    def test_load_run_not_found(self, tmp_path: Path):
        result = load_run("nonexistent", store_dir=str(tmp_path))
        assert result is None

    def test_to_dict(self, tmp_path: Path):
        run = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        d = run.to_dict()
        assert isinstance(d, dict)
        assert d["run_id"] == run.run_id
        assert d["results"][0]["model"] == "tiny"


# ── index management ────────────────────────────────────────────────────────


class TestIndex:
    def test_save_updates_index(self, tmp_path: Path):
        run = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        save_run(run, store_dir=str(tmp_path))
        index_path = Path(tmp_path) / "index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text())
        assert len(index) == 1
        assert index[0]["run_id"] == run.run_id

    def test_save_multiple_runs(self, tmp_path: Path):
        run1 = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        run2 = _make_run([_make_result("base", "simple", 0.98, 0.05)], str(tmp_path))
        save_run(run1, store_dir=str(tmp_path))
        save_run(run2, store_dir=str(tmp_path))
        index = json.loads((Path(tmp_path) / "index.json").read_text())
        assert len(index) == 2
        # Latest first
        assert index[0]["run_id"] == run2.run_id

    def test_load_index_missing_file(self, tmp_path: Path):
        # No index.json exists — list_runs should return empty
        runs = list_runs(str(tmp_path))
        assert runs == []

    def test_load_index_corrupted(self, tmp_path: Path):
        index_file = Path(tmp_path) / "index.json"
        index_file.write_text("not json {{{", encoding="utf-8")
        runs = list_runs(str(tmp_path))
        assert runs == []

    def test_load_index_partial_corruption(self, tmp_path: Path):
        index_file = Path(tmp_path) / "index.json"
        index_file.write_text(
            json.dumps(
                [
                    {"run_id": "run1", "timestamp": "2025-01-01"},
                    {"invalid_key": "missing run_id"},
                ]
            ),
            encoding="utf-8",
        )
        # list_runs will try load_run("run1") which fails gracefully
        runs = list_runs(str(tmp_path))
        assert len(runs) == 0  # run1 doesn't exist on disk


# ── list_runs ───────────────────────────────────────────────────────────────


class TestListRuns:
    def test_list_empty(self, tmp_path: Path):
        runs = list_runs(str(tmp_path))
        assert runs == []

    def test_list_returns_runs(self, tmp_path: Path):
        run = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        save_run(run, store_dir=str(tmp_path))
        runs = list_runs(str(tmp_path))
        assert len(runs) == 1
        assert runs[0].run_id == run.run_id

    def test_list_returns_all_in_order(self, tmp_path: Path):
        run1 = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        run2 = _make_run([_make_result("base", "simple", 0.98, 0.05)], str(tmp_path))
        save_run(run1, store_dir=str(tmp_path))
        save_run(run2, store_dir=str(tmp_path))
        runs = list_runs(str(tmp_path))
        assert len(runs) == 2
        assert runs[0].run_id == run2.run_id  # latest first


# ── diff_runs ───────────────────────────────────────────────────────────────


class TestDiffRuns:
    def test_diff_identical_runs(self, tmp_path: Path):
        run1 = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        run2 = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        save_run(run1, store_dir=str(tmp_path))
        save_run(run2, store_dir=str(tmp_path))
        diff = diff_runs(run1.run_id, run2.run_id, store_dir=str(tmp_path))
        assert "error" not in diff
        assert diff["total_changed"] == 0

    def test_diff_different_models(self, tmp_path: Path):
        run1 = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        save_run(run1, store_dir=str(tmp_path))
        import time

        time.sleep(1.1)  # ensure different run_id
        run2 = _make_run([_make_result("base", "simple", 0.98, 0.05)], str(tmp_path))
        save_run(run2, store_dir=str(tmp_path))
        diff = diff_runs(run1.run_id, run2.run_id, store_dir=str(tmp_path))
        added = [d for d in diff["diffs"] if d["status"] == "added"]
        removed = [d for d in diff["diffs"] if d["status"] == "removed"]
        assert len(added) >= 1
        assert len(removed) >= 1

    def test_diff_different_metrics(self, tmp_path: Path):
        results1 = [_make_result("tiny", "simple", 0.90, 0.20)]
        run1 = _make_run(results1, str(tmp_path))
        save_run(run1, store_dir=str(tmp_path))
        import time

        time.sleep(1.1)  # ensure different run_id
        results2 = [_make_result("tiny", "simple", 0.95, 0.10)]
        run2 = _make_run(results2, str(tmp_path))
        save_run(run2, store_dir=str(tmp_path))
        diff = diff_runs(run1.run_id, run2.run_id, store_dir=str(tmp_path))
        assert diff["total_changed"] == 1
        d = diff["diffs"][0]
        assert d["status"] == "changed"
        assert d["lev_diff"] == 0.05
        assert d["wer_diff"] == -0.10

    def test_diff_missing_category(self, tmp_path: Path):
        results1 = [_make_result("tiny", "simple", 0.90, 0.20)]
        run1 = _make_run(results1, str(tmp_path))
        save_run(run1, store_dir=str(tmp_path))
        import time

        time.sleep(1.1)  # ensure different run_id
        results2 = [_make_result("tiny", "complex", 0.85, 0.25)]
        run2 = _make_run(results2, str(tmp_path))
        save_run(run2, store_dir=str(tmp_path))
        diff = diff_runs(run1.run_id, run2.run_id, store_dir=str(tmp_path))
        added = [d for d in diff["diffs"] if d["status"] == "added"]
        removed = [d for d in diff["diffs"] if d["status"] == "removed"]
        assert len(added) == 1
        assert len(removed) == 1

    def test_diff_run_not_found(self, tmp_path: Path):
        diff = diff_runs("nonexistent_a", "nonexistent_b", store_dir=str(tmp_path))
        assert "error" in diff
        assert "not found" in diff["error"].lower()


# ── print_diff ──────────────────────────────────────────────────────────────


class TestPrintDiff:
    def test_print_diff_error(self):
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            print_diff({"error": "Run not found"})
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        assert "Error" in output

    def test_print_diff_outputs_text(self, tmp_path: Path):
        run1 = _make_run([_make_result("tiny", "simple", 0.90, 0.20)], str(tmp_path))
        run2 = _make_run([_make_result("tiny", "simple", 0.95, 0.10)], str(tmp_path))
        save_run(run1, store_dir=str(tmp_path))
        save_run(run2, store_dir=str(tmp_path))
        diff = diff_runs(run1.run_id, run2.run_id, store_dir=str(tmp_path))
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            print_diff(diff)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        assert "changed" in output.lower() or "changed" in output.lower()


# ── CLI commands ────────────────────────────────────────────────────────────


class TestStoreCLI:
    def test_cli_save(self, tmp_path: Path):
        """Test the 'save' CLI subcommand via direct function call."""
        result_file = tmp_path / "results.json"
        result_file.write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "model": "tiny",
                            "category": "simple",
                            "levenshtein": 0.95,
                            "wer": 0.10,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        old_argv = sys.argv
        sys.argv = [
            "store.py",
            "save",
            str(result_file),
            "--models",
            "tiny",
            "--voices",
            "cosette",
            "--store-dir",
            str(tmp_path),
        ]
        try:
            main()
        finally:
            sys.argv = old_argv
        index = json.loads((Path(tmp_path) / "index.json").read_text())
        assert len(index) == 1

    def test_cli_save_invalid_json(self, tmp_path: Path):
        """Test save with invalid JSON file."""
        result_file = tmp_path / "bad.json"
        result_file.write_text("not json {{{", encoding="utf-8")
        old_argv = sys.argv
        sys.argv = ["store.py", "save", str(result_file), "--models", "tiny", "--store-dir", str(tmp_path)]
        try:
            main()
        finally:
            sys.argv = old_argv
        # Should not crash — handled gracefully
        assert not (Path(tmp_path) / "index.json").exists()

    def test_cli_list_empty(self, tmp_path: Path):
        """Test list command with no stored runs."""
        runs = list_runs(str(tmp_path))
        assert runs == []

    def test_cli_list_after_save(self, tmp_path: Path):
        """Test list command shows saved run."""
        result_file = tmp_path / "results.json"
        result_file.write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "model": "tiny",
                            "category": "simple",
                            "levenshtein": 0.95,
                            "wer": 0.10,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        old_argv = sys.argv
        sys.argv = [
            "store.py",
            "save",
            str(result_file),
            "--models",
            "tiny",
            "--voices",
            "cosette",
            "--store-dir",
            str(tmp_path),
        ]
        try:
            main()
        finally:
            sys.argv = old_argv
        runs = list_runs(str(tmp_path))
        assert len(runs) == 1
        assert "tiny" in runs[0].stt_models[0]

    def test_cli_diff(self, tmp_path: Path):
        """Test diff command between two runs."""
        import sys

        results1 = tmp_path / "results1.json"
        results1.write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "model": "tiny",
                            "category": "simple",
                            "levenshtein": 0.90,
                            "wer": 0.20,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        results2 = tmp_path / "results2.json"
        results2.write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "model": "tiny",
                            "category": "simple",
                            "levenshtein": 0.95,
                            "wer": 0.10,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        old_argv = sys.argv
        sys.argv = [
            "store.py",
            "save",
            str(results1),
            "--models",
            "tiny",
            "--voices",
            "cosette",
            "--store-dir",
            str(tmp_path),
        ]
        try:
            main()
        finally:
            sys.argv = old_argv
        time.sleep(1.1)
        sys.argv = [
            "store.py",
            "save",
            str(results2),
            "--models",
            "tiny",
            "--voices",
            "cosette",
            "--store-dir",
            str(tmp_path),
        ]
        try:
            main()
        finally:
            sys.argv = old_argv
        # Get the two run IDs from index
        index = json.loads((Path(tmp_path) / "index.json").read_text())
        assert len(index) == 2
        diff = diff_runs(index[1]["run_id"], index[0]["run_id"], store_dir=str(tmp_path))
        assert "error" not in diff
