#!/bin/bash
# ziomek launcher script
# Runs the ziomek TTS + avatar server via uv

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Change to project root
cd "$SCRIPT_DIR"

# Start the server (port from argument or default 5003)
uv run python -m ziomek.cli serve --port "${1:-5003}" "$@"
