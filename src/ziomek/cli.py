"""ziomek CLI — unified command-line interface.

Usage:
    ziomek                           Start ziomek client (default)
    ziomek --server                  Start TTS server
    ziomek --client                  Start ziomek client
    ziomek --scaffold-config         Create default ziomek_config.yaml and exit
"""

import argparse
from importlib.metadata import version as get_version

from ziomek.server import run_server

# Lazy import to avoid loading the client module unless --client is used
_ziomek_client_cli = None


def _import_client_cli():
    global _ziomek_client_cli
    if _ziomek_client_cli is None:
        from ziomek.client import cli as _ziomek_client_cli
    return _ziomek_client_cli


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
    )


def scaffold_cmd(args):
    from ziomek.config import Settings

    path = Settings.scaffold_config("ziomek_config.yaml")
    print(f"Config file created at {path}")


def client_cmd(args):
    client_cli = _import_client_cli()
    client_cli.main()


def _default_main():
    client_cli = _import_client_cli()
    client_cli.main()


def main():
    parser = argparse.ArgumentParser(prog="ziomek", description="Humanize AI backend")
    parser.add_argument("--version", action="version", version=f"%(prog)s {get_version('ziomek')}")

    # Top-level mode flags
    parser.add_argument("--server", action="store_true", help="Start TTS server (default port: 5003)")
    parser.add_argument("--client", action="store_true", help="Start ziomek client (default port: 5004)")

    # -- server args --
    parser.add_argument("--port", type=int, default=None, help="Port (5003 for server, 5004 for client)")
    parser.add_argument("--model-path", type=str, default=None, help="Path to TTS model")
    parser.add_argument("--voice", type=str, default="default", help="Voice to use (default: default)")
    parser.add_argument("--cache-dir", type=str, default=None, help="Cache directory for TTS")
    parser.add_argument(
        "--audio-backend",
        type=str,
        default=None,
        help="Audio playback backend (sounddevice, pygame, pyaudio, playsound, rtmixer, noop)",
    )
    parser.add_argument("--audio-device", type=str, default=None, help="Audio device index, name, or 'default'")
    parser.add_argument("--host", type=str, default=None, help="Host to bind (default: localhost)")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # -- client args --
    parser.add_argument("--no-vscode", action="store_true", help="Disable VS Code WebSocket relay")
    parser.add_argument("--no-browser", action="store_true", help="Do not open local browser")
    parser.add_argument(
        "--server-url",
        type=str,
        default="http://localhost:5003",
        help="ziomek TTS server URL (default: http://localhost:5003)",
    )

    # -- STT args --
    parser.add_argument(
        "--stt-engine",
        type=str,
        default=None,
        help="STT engine (whisper_cpp, faster_whisper)",
    )
    parser.add_argument(
        "--stt-model",
        type=str,
        default=None,
        help="STT model (tiny.en, base.en, small.en)",
    )
    parser.add_argument(
        "--stt-model-dir",
        type=str,
        default=None,
        help="STT model download directory",
    )

    # -- config --
    parser.add_argument(
        "--scaffold-config",
        action="store_true",
        help="Create a default ziomek_config.yaml and exit",
    )

    args = parser.parse_args()

    if args.scaffold_config:
        scaffold_cmd(args)
    elif args.server or not args.client:
        # Default to server unless --client is explicitly set
        serve_cmd(args)
    else:
        client_cmd(args)


if __name__ == "__main__":
    main()
