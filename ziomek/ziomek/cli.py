"""ziomek CLI — command-line interface.

Usage:
    ziomek serve       Start TTS server (port 5003)
    ziomek client      Start ziomek client (port 5004, gamepad + avatar display)
    ziomek             Start ziomek client (default)
"""
import argparse

from ziomek.server import run_server

# Lazy import to avoid loading the client module unless --client is used
_ziomek_client_cli = None


def _import_client_cli():
    global _ziomek_client_cli
    if _ziomek_client_cli is None:
        from ziomek.client import cli as _ziomek_client_cli
    return _ziomek_client_cli


def serve_cmd(args):
    run_server(port=args.port, model_path=args.model_path,
        voice=args.voice, cache_dir=args.cache_dir)


def client_cmd(args):
    client_cli = _import_client_cli()
    client_cli.main()


def _default_main():
    client_cli = _import_client_cli()
    client_cli.main()


def main():
    parser = argparse.ArgumentParser(prog="ziomek", description="Humanize AI backend")
    parser.add_argument("--version", action="version",
        version=f"%(prog)s {__import__('ziomek').__version__}")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # -- server --
    serve = sub.add_parser("serve", help="Start TTS server (port 5003)")
    serve.add_argument("--port", type=int, default=5003)
    serve.add_argument("--model-path", type=str, default=None)
    serve.add_argument("--voice", type=str, default="default")
    serve.add_argument("--cache-dir", type=str, default=None)
    serve.set_defaults(func=serve_cmd)

    # -- client --
    client = sub.add_parser("client", help="Start ziomek client (gamepad + avatar display, port 5004)")
    client.add_argument("--port", type=int, default=5004)
    client.add_argument("--no-vscode", action="store_true",
        help="Disable VS Code WebSocket relay")
    client.add_argument("--no-browser", action="store_true",
        help="Do not open local browser")
    client.add_argument("--server-url", type=str,
        default="http://localhost:5003",
        help="ziomek TTS server URL (default: http://localhost:5003)")
    client.set_defaults(func=client_cmd)

    args = parser.parse_args()
    if args.command in ("serve", "client"):
        args.func(args)
    else:
        # No subcommand — default to client
        _default_main()


if __name__ == "__main__":
    main()
