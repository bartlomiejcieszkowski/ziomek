# Changelog

All notable changes to this project are documented here.

## [0.4.3] - 2026-10-30

### Changed

- Data files (pages and sprite sheet) live in one folder, `src/ziomek/resources`, and the code builds paths from it
- Generated config files (`ziomek_config.yaml`, `ziomek_server_config.yaml`) are no longer tracked in git

### Fixed

- The release build: `[tool.hatch.build] only-packages` dropped data files from the sdist, and CI builds the wheel from that sdist, so `uv build` failed with `Forced include not found: src/ziomek/resources`; the force-include now applies to the sdist as well as the wheel
- Stale default port in the launcher scripts, which still showed `5003` instead of `5004`

## [0.4.2] - 2026-10-29

### Fixed

- Installed wheel ships the page assets and the sprite sheet through `[tool.hatch.build.targets.wheel.force-include]`; `only-packages` dropped them, so an installed package answered 404 for the avatar view under `uvx`
- Packaging guard test reads `pyproject.toml` with `tomllib` so data files cannot be dropped from the wheel again

## [0.4.1] - 2026-10-29

### Fixed

- Avatar view page restored, with `/api/avatar/ws` pushing the current expression to connected clients
- STT callbacks scheduled on the event loop captured at startup instead of the running loop
- The STT worker's shutdown-time connection error is logged at debug level only; genuine errors stay visible

## [0.4.0] - 2026-10-28

### Added

- `--no-stt` flag and `no_stt` config key; the STT engine is created only when the optional `stt` extra is installed, and the install hint names `ziomek[stt]` rather than the library alone
- CLI exits with an error when MCP flags are used without the `mcp` package installed
- `--no-browser` now works: the served avatar page is opened on successful startup unless it is set
- File-based transcription path (`start_from_file()`) for benchmarks and tests; microphone mode is unchanged for the server
- STT benchmark results record the voice used; summary and CSV group by voice, model, and category
- `ruff format` gate in CI, with formatting applied across the codebase

### Changed

- `--no-vscode` renamed to `--no-gamepad` (its only real effect was skipping gamepad polling); stale `no_vscode` keys in existing config files are ignored — breaking for flag users
- Default-port references corrected to 5004 in CLI help, the config scaffold, docstrings, and the pi-ziomek client defaults
- Benchmark per-iteration output moved to debug level; the summary prints the test text snippet
- `.gitignore` narrowed from all `*.csv` to `tts_accuracy.csv` plus `benchmarks/`

### Fixed

- MCP HTTP endpoint answers JSON-RPC at `/mcp` (it returned 405); the session manager runs inside the app lifespan; the info page moved to `/mcp/info`; `/mcp/sse` and `/mcp/message` stay as aliases
- RealtimeSTT worker processes are reaped on stop, so pytest no longer hangs at exit on Windows
- Audio handed to transcription is normalized float32 (int16 caused ONNX dtype errors)
- TTS model is loaded before the accuracy benchmark runs
- Missing `.close()` on FasterWhisperEngine suppressed during shutdown
- Third-party loggers (RealtimeSTT, whisper, ctranslate2, torch) silenced; stdout and stderr wrapped as UTF-8 for non-ASCII transcriptions
- pi-ziomek TTS client calls the endpoints the server actually exposes (`/generate`, `/speak`, `/voices`); unsupported `cancel()` and `getLastWavPath()` removed
- MCP server version reads from `VERSION` instead of a hardcoded string

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
