"""ziomek CLI — unified command-line interface.

Usage:
    ziomek                           Start ziomek server (default)
    ziomek --scaffold-config         Create default ziomek_config.yaml and exit
    ziomek benchmark list            List saved benchmark runs
    ziomek benchmark diff <A> <B>    Compare two benchmark runs
"""

import argparse
from importlib.metadata import version as get_version

from ziomek.server import run_server


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
        mcp_enabled=args.mcp,
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


def benchmark_cmd(args):
    """Handle benchmark subcommands."""
    if args.benchmark_command == "list":
        benchmark_list_cmd(args)
    elif args.benchmark_command == "diff":
        benchmark_diff_cmd(args)
    else:
        args.benchmark_parser.print_help()


def main():
    parser = argparse.ArgumentParser(prog="ziomek", description="Humanize AI backend")
    parser.add_argument("--version", action="version", version=f"%(prog)s {get_version('ziomek')}")

    # Server args
    parser.add_argument("--port", type=int, default=None, help="Port (default: 5003)")
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
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Enable MCP server alongside HTTP server",
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

    benchmark_list_parser = benchmark_parser.add_parser(
        "benchmark", help="Benchmark management",
    )
    benchmark_sub = benchmark_list_parser.add_subparsers(dest="benchmark_command")

    benchmark_list_parser = benchmark_sub.add_parser(
        "list", help="List saved benchmark runs",
    )
    benchmark_list_parser.add_argument(
        "--store-dir", default="benchmarks",
        help="Benchmark store directory",
    )
    benchmark_list_parser.set_defaults(func=benchmark_list_cmd)

    benchmark_diff_parser = benchmark_sub.add_parser(
        "diff", help="Compare two benchmark runs",
    )
    benchmark_diff_parser.add_argument("run_a", help="First run ID")
    benchmark_diff_parser.add_argument("run_b", help="Second run ID")
    benchmark_diff_parser.add_argument(
        "--store-dir", default="benchmarks",
        help="Benchmark store directory",
    )
    benchmark_diff_parser.set_defaults(func=benchmark_diff_cmd)

    args = parser.parse_args()

    if args.scaffold_config:
        scaffold_cmd(args)
    elif args.benchmark_command in ("list", "diff"):
        benchmark_cmd(args)
    else:
        serve_cmd(args)


if __name__ == "__main__":
    main()
