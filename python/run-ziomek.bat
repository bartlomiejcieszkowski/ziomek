@echo off
REM ziomek launcher script (Windows)
REM Runs the ziomek TTS + avatar server via uv

REM Change to project root (one level up)
cd /d "%~dp0.."

REM Start the server (port from argument or default 5003)
uv run python -m ziomek.cli serve --port %1
