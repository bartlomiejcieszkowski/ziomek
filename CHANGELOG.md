# Changelog

All notable changes to this project are documented here.

## [0.3.0] - 2026-10-22

### Added

- Merged server and client into single process (port 5004)
- STT streaming endpoint via WebSocket (`/api/stt/stream`) for live transcription
- STT HTTP API: status, start, stop, transcribe, reconfigure, models endpoints
- STT engine reconfiguration at runtime (engine/model switching)
- Debug mode (`--dev`) with debug endpoints and debug webpage
- Verbose logging (`--verbose`/`-v`) with STT event logging
- Colored stdout logging (uvicorn-style) with JSON log files
- Log ring buffer with `/api/debug/logs` and `/api/debug/logs/clear` endpoints
- Version centralization via single `VERSION` file at repo root
- Automated release workflow on VERSION bump
- Health endpoint enriched with STT info, audio backend/device, cache stats
- Request ID middleware for structured logging
- `conftest.py` with STT engine cleanup fixture for test isolation
- MCP server implementation with 8 tools (speak, transcribe, start/stop listening, transcription, set/get expression, status)
- MCP resources (voices, models, expressions, config) with read-only default
- MCP HTTP transport with streamable_http_app() (port-based routing)
- Benchmark CLI: `ziomek benchmark run tts|stt` with --store flag
- Benchmark result store with versioned history (save, list, diff)
- TTS accuracy round-trip benchmark (Levenshtein ratio + WER metrics)
- STT quality benchmark (Levenshtein ratio + WER metrics)
- BenchmarkWav output with configurable output directory
- Pi Voice Assistant extension scaffold (keyword gating, gamepad, dashboard)
- Marketplace config (plugin.json, mcp.json) for Agent Plugins 1.0
- UTF-8 stderr wrapping to handle non-ASCII STT transcription output

### Changed

- Default port changed from 5003 to 5004 (merged server/client)
- CLI unified: `ziomek` instead of `ziomek server`/`ziomek client`
- Config file renamed: `ziomek_server_config.yaml` → `ziomek_config.yaml` (backward compatible)
- Default STT engine changed from whisper_cpp to faster_whisper (whisper_cpp segfaults on Windows)
- STT engine starts recording immediately on startup

### Fixed

- Async transcription callback handling via `asyncio.run_coroutine_threadsafe`
- `transcribe_chunk` timeout to avoid blocking on RealtimeSTT.text()
- Debug endpoint JSON serialization for STTState enum
- WebSocket tests with proper mock engine setup

## [0.2.0] - 2026-09-30

### Added

- Pluggable audio playback backend system with support for sounddevice, pygame.mixer, pyaudio, playsound, python-rtmixer, and noop backends
- Configurable device selection by index, name, or system default
- YAML config file loading with `ziomek_server_config.yaml` (current dir)
- Configuration precedence: CLI flags > environment variables > config file > hardcoded defaults
- `scaffold-config` subcommand to generate default configuration files
- `IBackend` protocol for extensible audio backends
- OpenAPI documentation for ziomek server -- Swagger UI at `/docs` and ReDoc at `/redoc`
- OpenAPI documentation for ziomek client -- Swagger UI at `/docs` and ReDoc at `/redoc`
- Pydantic schemas for API request/response documentation

### Changed

- CORS now uses regex pattern `http://localhost:\d+` for proper origin matching
- Server version now read dynamically from package `__version__`

### Fixed

- Type annotation for `VoiceStateCache.cache_dir` to accept `str | None`
- `test_cors` — CORS headers now correctly returned for localhost requests
- PNG sprite test data generation for `test_skin_load_sprite_from_file`
- Added `excited` expression to skin registry
- Import sorting across 8+ files

## [0.1.2] - 2026-09-28

### Changed

- Updated version bump
- Added `readme` field to `pyproject.toml`

## [0.1.1] - 2026-09-28

### Changed

- Version bump

## [0.1.0] - 2026-09-27

### Added

- Standalone ziomek package with TTS synthesis, avatar state machine, and gamepad integration
- VS Code extension for gamepad-controlled avatar with TTS
- Launcher scripts for server management
- CI build workflow and PyPI publishing workflow
- MIT license file
