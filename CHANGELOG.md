# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- OpenAPI documentation for ziomek server — Swagger UI at `/docs` and ReDoc at `/redoc`
- OpenAPI documentation for ziomek client — Swagger UI at `/docs` and ReDoc at `/redoc`
- Pydantic schemas for API request/response documentation

### Changed

- CORS restricted to `http://localhost:*` instead of wildcard `*`
- Server version now read dynamically from package `__version__`

## [0.1.2] - 2025-xx-xx

### Changed

- Updated version bump
- Added `readme` field to `pyproject.toml`

## [0.1.1] - 2025-xx-xx

### Changed

- Version bump

## [0.1.0] - Initial Release

### Added

- Standalone ziomek package with TTS synthesis, avatar state machine, and gamepad integration
- VS Code extension for gamepad-controlled avatar with TTS
- Launcher scripts for server management
- CI build workflow and PyPI publishing workflow
- Apache 2.0 license
