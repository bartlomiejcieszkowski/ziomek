"""ziomek CLI — unified command-line interface.

Usage:
    ziomek                           Start ziomek server (default)
    ziomek --scaffold-config         Create default ziomek_config.yaml and exit
    ziomek benchmark list            List saved benchmark runs
    ziomek benchmark diff <A> <B>    Compare two benchmark runs
"""

import argparse
import sys
from importlib.metadata import version as get_version
from importlib.util import find_spec

from ziomek.server import run_server
from ziomek.stt import stt_installed


def mcp_installed() -> bool:
    """Return True if the optional 'mcp' package is importable."""
    return find_spec("mcp") is not None


def serve_cmd(args):
    run_server(
        port=args.port,
        model_path=args.model_path,
        voice=args.voice,
        cache_dir=args.cache_dir,
        audio_backend=args.audio_backend,
        audio_device=args.audio_device,
        host=args.host,
        log_level=args.log_level,
        no_vscode=args.no_vscode,
        no_browser=args.no_browser,
        stt_engine=args.stt_engine,
        stt_model=args.stt_model,
        stt_model_dir=args.stt_model_dir,
        dev_mode=args.dev,
        verbose=args.verbose,
        mcp_stdio=args.mcp_stdio,
        mcp_http=args.mcp,
        mcp_port=args.mcp_port,
        mcp_config_exposed=args.mcp_config,
    )


def scaffold_cmd(args):
    from ziomek.config import Settings

    path = Settings.scaffold_config("ziomek_config.yaml")
    print(f"Config file created at {path}")


def benchmark_list_cmd(args):
    from ziomek.benchmark.store import list_runs

    runs = list_runs(store_dir=args.store_dir)
    if not runs:
        print("No saved benchmark runs found.")
        return
    print(f"\n{'Run ID':<36} {'Timestamp':<22} {'Git Commit':<12} {'Models'}")
    print("-" * 100)
    for r in runs:
        models_str = ",".join(r.stt_models) if r.stt_models else "—"
        print(f"{r.run_id:<36} {r.timestamp:<22} {r.git_commit:<12} {models_str}")


def benchmark_diff_cmd(args):
    from ziomek.benchmark.store import diff_runs, print_diff

    diff = diff_runs(args.run_a, args.run_b, store_dir=args.store_dir)
    print_diff(diff)


def benchmark_run_cmd(args):
    """Run a benchmark (TTS accuracy or STT quality)."""
    if args.benchmark_type == "tts":
        # Run TTS accuracy benchmark
        from ziomek.tts.accuracy import main as accuracy_main

        accuracy_main(
            voices=args.voices,
            models=args.models,
            categories=args.categories,
            iterations=args.iterations,
            output=args.output,
            output_dir=args.output_dir,
            store=args.store,
            store_dir=args.store_dir,
            log_level=args.log_level,
        )
    elif args.benchmark_type == "stt":
        # Run STT quality benchmark
        from ziomek.stt.benchmark import main as stt_benchmark_main

        stt_benchmark_main(
            engines=args.engines,
            voices=args.voices,
            models=args.models,
            categories=args.categories,
            iterations=args.iterations,
            output_dir=args.output_dir,
            store=args.store,
            store_dir=args.store_dir,
            log_level=args.log_level,
        )
    else:
        args.benchmark_parser.print_help()


def benchmark_cmd(args):
    """Handle benchmark subcommands."""
    if args.benchmark_subcommand == "list":
        benchmark_list_cmd(args)
    elif args.benchmark_subcommand == "diff":
        benchmark_diff_cmd(args)
    elif args.benchmark_subcommand == "run":
        benchmark_run_cmd(args)
    else:
        # No subcommand — print help for the benchmark parser
        print("Usage: ziomek benchmark {list,diff,run} [options]")
        print()
        print("Benchmark management commands:")
        print("  list    List saved benchmark runs")
        print("  diff    Compare two benchmark runs")
        print("  run     Run a benchmark (TTS accuracy or STT quality)")


def main():
    parser = argparse.ArgumentParser(prog="ziomek", description="Humanize AI backend")
    parser.add_argument("--version", action="version", version=f"%(prog)s {get_version('ziomek')}")

    # Server args
    parser.add_argument("--port", type=int, default=None, help="Port (default: 5004)")
    parser.add_argument("--model-path", type=str, default=None, help="Path to TTS model")
    parser.add_argument("--voice", type=str, default="default", help="Voice to use (default: default)")
    parser.add_argument("--cache-dir", type=str, default=None, help="Cache directory for TTS")
    parser.add_argument(
        "--audio-backend",
        type=str,
        default=None,
        help="Audio playback backend (sounddevice, pygame, pyaudio, playsound, noop)",
    )
    parser.add_argument("--audio-device", type=str, default=None, help="Audio device index, name, or 'default'")
    parser.add_argument("--host", type=str, default=None, help="Host to bind (default: localhost)")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Client/feature flags
    parser.add_argument("--no-vscode", action="store_true", help="Disable VS Code WebSocket relay and gamepad polling")
    parser.add_argument("--no-browser", action="store_true", help="Do not open local browser")

    # STT args
    parser.add_argument(
        "--stt-engine",
        type=str,
        default=None,
        help="STT engine (faster_whisper)",
    )
    parser.add_argument(
        "--stt-model",
        type=str,
        default=None,
        help="STT model (tiny, base, small, medium)",
    )
    parser.add_argument(
        "--stt-model-dir",
        type=str,
        default=None,
        help="STT model download directory",
    )

    # Debug flags
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable debug mode: debug endpoints (/api/debug/*) and debug page (/debug)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )
    parser.add_argument(
        "--mcp-stdio",
        action="store_true",
        help="Enable MCP server in stdio mode alongside HTTP server",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Enable MCP server in HTTP mode alongside HTTP server",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=None,
        help="MCP HTTP server port (default: same as main server port)",
    )
    parser.add_argument(
        "--mcp-config",
        action="store_true",
        help="Expose full config via MCP (default: read-only)",
    )

    # Config
    parser.add_argument(
        "--scaffold-config",
        action="store_true",
        help="Create a default ziomek_config.yaml and exit",
    )

    # Benchmark subcommands
    benchmark_parser = parser.add_subparsers(dest="benchmark_command")

    benchmark_main = benchmark_parser.add_parser(
        "benchmark",
        help="Benchmark management",
    )
    benchmark_sub = benchmark_main.add_subparsers(dest="benchmark_subcommand")

    benchmark_list_parser = benchmark_sub.add_parser(
        "list",
        help="List saved benchmark runs",
    )
    benchmark_list_parser.add_argument(
        "--store-dir",
        default="benchmarks",
        help="Benchmark store directory",
    )
    benchmark_list_parser.set_defaults(func=benchmark_list_cmd)

    benchmark_diff_parser = benchmark_sub.add_parser(
        "diff",
        help="Compare two benchmark runs",
    )
    benchmark_diff_parser.add_argument("run_a", help="First run ID")
    benchmark_diff_parser.add_argument("run_b", help="Second run ID")
    benchmark_diff_parser.add_argument(
        "--store-dir",
        default="benchmarks",
        help="Benchmark store directory",
    )
    benchmark_diff_parser.set_defaults(func=benchmark_diff_cmd)

    # Run benchmark subcommand
    benchmark_run_parser = benchmark_sub.add_parser(
        "run",
        help="Run a benchmark (TTS accuracy or STT quality)",
    )
    benchmark_run_parser.set_defaults(benchmark_parser=benchmark_run_parser)
    benchmark_run_sub = benchmark_run_parser.add_subparsers(dest="benchmark_type")

    # TTS accuracy benchmark
    tts_parser = benchmark_run_sub.add_parser(
        "tts",
        help="Run TTS accuracy benchmark",
    )
    tts_parser.add_argument(
        "--voices",
        nargs="+",
        default=["cosette", "default"],
        help="Voices to test",
    )
    tts_parser.add_argument(
        "--models",
        nargs="+",
        default=["tiny", "tiny.en", "base", "base.en", "small", "small.en"],
        help="STT models to test",
    )
    tts_parser.add_argument(
        "--categories",
        nargs="+",
        default=["simple", "complex", "names", "numbers", "technical", "long"],
        help="Categories to test",
    )
    tts_parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Iterations per category per voice",
    )
    tts_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="CSV output file path",
    )
    tts_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save WAV files",
    )
    tts_parser.add_argument(
        "--store",
        action="store_true",
        help="Save benchmark results to store",
    )
    tts_parser.add_argument(
        "--store-dir",
        type=str,
        default="benchmarks",
        help="Benchmark store directory",
    )
    tts_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level",
    )
    tts_parser.set_defaults(func=benchmark_run_cmd)

    # STT quality benchmark
    stt_parser = benchmark_run_sub.add_parser(
        "stt",
        help="Run STT quality benchmark",
    )
    stt_parser.add_argument(
        "--engines",
        nargs="+",
        default=["faster_whisper"],
        help="STT engines to test",
    )
    stt_parser.add_argument(
        "--voices",
        nargs="+",
        default=["cosette", "default"],
        help="Voices to test",
    )
    stt_parser.add_argument(
        "--models",
        nargs="+",
        default=["tiny", "tiny.en", "base", "base.en", "small", "small.en"],
        help="STT models to test",
    )
    stt_parser.add_argument(
        "--categories",
        nargs="+",
        default=["simple", "complex", "names", "numbers", "technical", "long"],
        help="Categories to test",
    )
    stt_parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Iterations per category per voice",
    )
    stt_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save CSV/JSON output",
    )
    stt_parser.add_argument(
        "--store",
        action="store_true",
        help="Save benchmark results to store",
    )
    stt_parser.add_argument(
        "--store-dir",
        type=str,
        default="benchmarks",
        help="Benchmark store directory",
    )
    stt_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level",
    )
    stt_parser.set_defaults(func=benchmark_run_cmd)

    args = parser.parse_args()

    if (args.mcp or args.mcp_stdio) and not mcp_installed():
        print("Error: MCP support requires the 'mcp' package, which is not installed.", file=sys.stderr)
        print("Install it with: uv pip install 'ziomek[mcp]' (or run without --mcp / --mcp-stdio).", file=sys.stderr)
        sys.exit(1)

    # Option 3: warn and continue — the server runs with STT disabled.
    if not stt_installed():
        print(
            'Warning: STT support requires the "stt" extra, which is not installed. '
            'Install it with: uv pip install "ziomek[stt]" — STT will be disabled for this run.',
            file=sys.stderr,
        )

    if args.scaffold_config:
        scaffold_cmd(args)
    elif args.benchmark_command == "benchmark":
        benchmark_cmd(args)
    else:
        serve_cmd(args)


if __name__ == "__main__":
    main()
