"""ziomek CLI — command-line interface."""
import argparse
import sys
from ziomek.server import run_server


def main():
    parser = argparse.ArgumentParser(prog="ziomek", description="Humanize AI backend")
    parser.add_argument("--version", action="version",
        version=f"%(prog)s {__import__('ziomek').__version__}")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="Start HTTP server")
    serve.add_argument("--port", type=int, default=5003)
    serve.add_argument("--model-path", type=str, default=None)
    serve.add_argument("--voice", type=str, default="default")
    serve.add_argument("--cache-dir", type=str, default=None)
    args = parser.parse_args()
    if args.command == "serve" or args.command is None:
        run_server(port=args.port, model_path=args.model_path,
            voice=args.voice, cache_dir=args.cache_dir)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
