#!/bin/bash
# ziomek launcher script
# Runs the ziomek TTS + avatar server

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Install ziomek if not already installed
pip install -e "$SCRIPT_DIR" --quiet 2>/dev/null || true

# Start the server (port from argument or default 5003)
exec python -m ziomek.cli serve --port "${1:-5003}" "$@"
