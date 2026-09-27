@echo off
REM ziomek launcher script (Windows)
REM Runs the ziomek TTS + avatar server

cd /d "%~dp0"

REM Install ziomek if not already installed
pip install -e . --quiet 2>nul || true

REM Start the server (port from argument or default 5003)
python -m ziomek.cli serve --port %1
