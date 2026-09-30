"""ziomek CLI — command-line interface.

Usage:
    ziomek server      Start TTS server (port 5003)
    ziomek client      Start ziomek client (port 5004, gamepad + avatar display)
    ziomek             Start ziomek client (default)
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
    )


def scaffold_cmd(args):
    from ziomek.config import Settings

    path = Settings.scaffold_config("ziomek_server_config.yaml")
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
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # -- server (primary) --
    server_cmd = sub.add_parser("server", help="Start TTS server (port 5003)")
    server_cmd.add_argument("--port", type=int, default=5003)
    server_cmd.add_argument("--model-path", type=str, default=None)
    server_cmd.add_argument("--voice", type=str, default="default")
    server_cmd.add_argument("--cache-dir", type=str, default=None)
    server_cmd.add_argument(
        "--audio-backend",
        type=str,
        default=None,
        help="Audio playback backend (sounddevice, pygame, pyaudio, playsound, rtmixer, noop)",
    )
    server_cmd.add_argument("--audio-device", type=str, default=None, help="Audio device index, name, or 'default'")
    server_cmd.set_defaults(func=serve_cmd)

    # -- serve (deprecated alias for server) --
    serve = sub.add_parser("serve", help="Start TTS server (port 5003) [deprecated, use 'server']")
    serve.add_argument("--port", type=int, default=5003)
    serve.add_argument("--model-path", type=str, default=None)
    serve.add_argument("--voice", type=str, default="default")
    serve.add_argument("--cache-dir", type=str, default=None)
    serve.add_argument(
        "--audio-backend",
        type=str,
        default=None,
        help="Audio playback backend (sounddevice, pygame, pyaudio, playsound, rtmixer, noop)",
    )
    serve.add_argument("--audio-device", type=str, default=None, help="Audio device index, name, or 'default'")
    serve.set_defaults(func=serve_cmd)

    # -- client --
    client = sub.add_parser("client", help="Start ziomek client (gamepad + avatar display, port 5004)")
    client.add_argument("--port", type=int, default=5004)
    client.add_argument("--no-vscode", action="store_true", help="Disable VS Code WebSocket relay")
    client.add_argument("--no-browser", action="store_true", help="Do not open local browser")
    client.add_argument(
        "--server-url",
        type=str,
        default="http://localhost:5003",
        help="ziomek TTS server URL (default: http://localhost:5003)",
    )
    client.set_defaults(func=client_cmd)

    # -- scaffold-config --
    scaffold = sub.add_parser(
        "scaffold-config",
        help="Create a default ziomek_server_config.yaml in the current directory",
    )
    scaffold.set_defaults(func=scaffold_cmd)

    args = parser.parse_args()
    if args.command in ("server", "serve", "client", "scaffold-config"):
        args.func(args)
    else:
        # No subcommand — default to client
        _default_main()


if __name__ == "__main__":
    main()
