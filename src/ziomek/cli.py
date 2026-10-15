"""ziomek CLI — unified command-line interface.

Usage:
    ziomek                           Start ziomek server (default)
    ziomek --scaffold-config         Create default ziomek_config.yaml and exit
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
    )


def scaffold_cmd(args):
    from ziomek.config import Settings

    path = Settings.scaffold_config("ziomek_config.yaml")
    print(f"Config file created at {path}")


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
        help="STT model (tiny.en, base.en, small.en)",
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

    # Config
    parser.add_argument(
        "--scaffold-config",
        action="store_true",
        help="Create a default ziomek_config.yaml and exit",
    )

    args = parser.parse_args()

    if args.scaffold_config:
        scaffold_cmd(args)
    else:
        serve_cmd(args)


if __name__ == "__main__":
    main()
