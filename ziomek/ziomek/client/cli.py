"""ziomek-client CLI — gamepad polling + avatar display launcher.

Usage:
    ziomek-client                    # Start with browser + VS Code relay
    ziomek-client --no-browser       # VS Code relay only
    ziomek-client --no-vscode        # Browser only
    ziomek-client --no-vscode --no-browser  # Standalone display only
    ziomek-client --server-url http://remote:5003  # Remote TTS server
"""
from __future__ import annotations

import argparse
import sys

from ziomek.client.server import ZiomekClientApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ziomek-client",
        description="ziomek client — gamepad polling + avatar display",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5004,
        help="Client HTTP/WebSocket port (default: 5004)",
    )
    parser.add_argument(
        "--no-vscode",
        action="store_true",
        help="Disable WebSocket relay to VS Code (default: relay enabled)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open local browser (default: opens browser)",
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default="http://localhost:5003",
        help="ziomek TTS server URL (default: http://localhost:5003)",
    )
    args = parser.parse_args()

    open_browser = not args.no_browser
    open_browser_str = "yes" if open_browser else "no"

    client = ZiomekClientApp(
        server_url=args.server_url,
        port=args.port,
        open_browser=open_browser,
    )

    print(f"[ziomek client] Starting on port {args.port}", file=sys.stderr)
    print(f"[ziomek client] Sprite server: {args.server_url}", file=sys.stderr)
    print(f"[ziomek client] Open browser: {open_browser_str}", file=sys.stderr)

    try:
        client.start()
    except KeyboardInterrupt:
        print("\n[ziomek client] Shutting down...", file=sys.stderr)
        client.stop()


if __name__ == "__main__":
    main()
