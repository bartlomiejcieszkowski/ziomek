# Changelog

All notable changes to this project are documented here.

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
- Apache 2.0 license
