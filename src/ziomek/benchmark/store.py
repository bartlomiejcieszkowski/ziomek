"""ziomek benchmark result store — versioned history for comparing results."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkRun:
    """A single benchmark run with metadata."""

    run_id: str  # ISO timestamp
    timestamp: str  # ISO 8601
    python_version: str
    platform: str
    # Library versions
    pocket_tts_version: str = ""
    faster_whisper_version: str = ""
    realtimestt_version: str = ""
    torch_version: str = ""
    # Model info
    stt_models: list[str] = field(default_factory=list)
    stt_engines: list[str] = field(default_factory=list)
    tts_voices: list[str] = field(default_factory=list)
    # Git info
    git_commit: str = ""
    git_branch: str = ""
    # Results
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_git_info() -> tuple[str, str]:
    """Get current git commit and branch."""
    commit = "unknown"
    branch = "unknown"
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    try:
        branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return commit, branch


def _get_package_version(name: str) -> str:
    """Get package version from pip or importlib."""
    try:
        from importlib.metadata import version  # noqa: F401

        return version(name)
    except Exception:
        try:
            return (
                subprocess.check_output(
                    ["pip", "show", name],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .split("\n")[1]
                .split(":")[1]
                .strip()
            )
        except Exception:
            return "unknown"


def create_run(
    results: list[dict[str, Any]],
    stt_models: list[str] | None = None,
    stt_engines: list[str] | None = None,
    tts_voices: list[str] | None = None,
) -> BenchmarkRun:
    """Create a new benchmark run with metadata."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return BenchmarkRun(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        python_version=__import__("sys").version,
        platform=__import__("sys").platform,
        pocket_tts_version=_get_package_version("pocket-tts"),
        faster_whisper_version=_get_package_version("faster-whisper"),
        realtimestt_version=_get_package_version("realtimestt"),
        torch_version=_get_package_version("torch"),
        stt_models=stt_models or [],
        stt_engines=stt_engines or [],
        tts_voices=tts_voices or [],
        git_commit=_get_git_info()[0],
        git_branch=_get_git_info()[1],
        results=results,
    )


def save_run(run: BenchmarkRun, store_dir: str = "benchmarks") -> Path:
    """Save a benchmark run to disk."""
    store = Path(store_dir)
    store.mkdir(parents=True, exist_ok=True)

    # Save individual run
    run_path = store / f"{run.run_id}.json"
    try:
        with open(run_path, "w") as f:
            json.dump(run.to_dict(), f, indent=2)
    except OSError:
        logger.exception("Failed to save run %s", run.run_id)
        return run_path

    # Update index (latest runs first)
    index_path = store / "index.json"
    index: list[dict[str, Any]] = []
    if index_path.exists():
        try:
            with open(index_path, "r") as f:
                index = json.load(f)
        except (OSError, json.JSONDecodeError):
            index = []
    index.insert(0, {"run_id": run.run_id, "timestamp": run.timestamp})
    try:
        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)
    except OSError:
        logger.exception("Failed to update index")

    logger.info("Saved benchmark run: %s → %s", run.run_id, run_path)
    return run_path


def load_run(run_id: str, store_dir: str = "benchmarks") -> BenchmarkRun | None:
    """Load a benchmark run by ID."""
    run_path = Path(store_dir) / f"{run_id}.json"
    if not run_path.exists():
        return None
    try:
        with open(run_path, "r") as f:
            data = json.load(f)
        return BenchmarkRun(**data)
    except (OSError, json.JSONDecodeError):
        return None


def list_runs(store_dir: str = "benchmarks") -> list[BenchmarkRun]:
    """List all saved benchmark runs."""
    store = Path(store_dir)
    if not store.exists():
        return []

    runs: list[BenchmarkRun] = []
    index_path = store / "index.json"
    if index_path.exists():
        try:
            with open(index_path, "r") as f:
                index = json.load(f)
            for entry in index:
                run_id = entry.get("run_id")
                if not run_id:
                    continue
                run = load_run(run_id, store_dir)
                if run:
                    runs.append(run)
        except (OSError, json.JSONDecodeError):
            pass
    return runs


def diff_runs(run_a_id: str, run_b_id: str, store_dir: str = "benchmarks") -> dict[str, Any]:
    """Compare two benchmark runs and return differences."""
    run_a = load_run(run_a_id, store_dir)
    run_b = load_run(run_b_id, store_dir)

    if not run_a or not run_b:
        return {"error": "One or both runs not found"}

    # Compare by model+category
    def key(r: dict) -> str:
        return f"{r.get('engine', '')}/{r.get('model', '')}/{r.get('category', '')}"

    results_a = {key(r): r for r in run_a.results}
    results_b = {key(r): r for r in run_b.results}

    diffs: list[dict[str, Any]] = []
    all_keys = set(results_a) | set(results_b)

    for k in sorted(all_keys):
        a = results_a.get(k)
        b = results_b.get(k)

        if a and not b:
            diffs.append({"key": k, "status": "removed", "run_a": a})
        elif b and not a:
            diffs.append({"key": k, "status": "added", "run_b": b})
        else:
            a_lev = a.get("levenshtein", 0) if a else 0
            b_lev = b.get("levenshtein", 0) if b else 0
            a_wer = a.get("wer", 0) if a else 0
            b_wer = b.get("wer", 0) if b else 0
            lev_diff = b_lev - a_lev
            wer_diff = b_wer - a_wer
            if abs(lev_diff) > 0.001 or abs(wer_diff) > 0.001:
                diffs.append(
                    {
                        "key": k,
                        "status": "changed",
                        "run_a_lev": a_lev,
                        "run_b_lev": b_lev,
                        "lev_diff": round(lev_diff, 4),
                        "run_a_wer": a_wer,
                        "run_b_wer": b_wer,
                        "wer_diff": round(wer_diff, 4),
                    }
                )

    return {
        "run_a": {"id": run_a.run_id, "timestamp": run_a.timestamp, "git": run_a.git_commit},
        "run_b": {"id": run_b.run_id, "timestamp": run_b.timestamp, "git": run_b.git_commit},
        "total_compared": len(all_keys),
        "total_changed": len(diffs),
        "diffs": diffs,
    }


def print_diff(diff: dict[str, Any]) -> None:
    """Print a human-readable diff."""
    if "error" in diff:
        print(f"Error: {diff['error']}")
        return

    print("\n" + "=" * 80)
    print("Benchmark Diff")
    print("=" * 80)
    print(f"Run A: {diff['run_a']['id']} ({diff['run_a']['timestamp']})")
    print(f"Run B: {diff['run_b']['id']} ({diff['run_b']['timestamp']})")
    print(f"Compared: {diff['total_compared']} configs, {diff['total_changed']} changed")

    for d in diff["diffs"]:
        if d["status"] == "added":
            print(f"\n  + Added: {d['key']}")
        elif d["status"] == "removed":
            print(f"\n  - Removed: {d['key']}")
        else:
            lev_sign = "+" if d["lev_diff"] > 0 else ""
            wer_sign = "+" if d["wer_diff"] > 0 else ""
            print(f"\n  ~ {d['key']}:")
            print(f"    Levenshtein: {d['run_a_lev']:.4f} → {d['run_b_lev']:.4f} ({lev_sign}{d['lev_diff']:.4f})")
            print(f"    WER:         {d['run_a_wer']:.4f} → {d['run_b_wer']:.4f} ({wer_sign}{d['wer_diff']:.4f})")

    print("\n" + "=" * 80)


def main() -> None:
    """CLI entry point for benchmark store."""
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark Result Store")
    sub = parser.add_subparsers(dest="command")

    # save
    save_parser = sub.add_parser("save", help="Save benchmark results")
    save_parser.add_argument("file", help="JSON file with results")
    save_parser.add_argument("--models", nargs="+", default=None)
    save_parser.add_argument("--engines", nargs="+", default=None)
    save_parser.add_argument("--voices", nargs="+", default=None)
    save_parser.add_argument("--store-dir", default="benchmarks")

    # list
    list_parser = sub.add_parser("list", help="List saved runs")
    list_parser.add_argument("--store-dir", default="benchmarks")

    # diff
    diff_parser = sub.add_parser("diff", help="Compare two runs")
    diff_parser.add_argument("run_a", help="First run ID")
    diff_parser.add_argument("run_b", help="Second run ID")
    diff_parser.add_argument("--store-dir", default="benchmarks")

    args = parser.parse_args()

    if args.command == "save":
        try:
            with open(args.file, "r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Error reading {args.file}: {e}")
            return
        results = data.get("results", [])
        run = create_run(
            results=results,
            stt_models=args.models,
            stt_engines=args.engines,
            tts_voices=args.voices,
        )
        path = save_run(run, store_dir=args.store_dir)
        print(f"Saved: {path}")

    elif args.command == "list":
        runs = list_runs(store_dir=args.store_dir)
        for r in runs:
            print(f"{r.run_id}  {r.timestamp}  git:{r.git_commit}  models:{','.join(r.stt_models)}")

    elif args.command == "diff":
        diff = diff_runs(args.run_a, args.run_b, store_dir=args.store_dir)
        print_diff(diff)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
