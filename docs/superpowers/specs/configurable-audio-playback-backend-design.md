# Configurable Audio Playback Backend — Design Spec

**Date:** 2025-01-04
**Status:** Approved by user
**Scope:** Server-side only (client follows as a separate task)

## Problem

ziomek's TTS playback is hardcoded to `sounddevice` with no way to select an alternative backend or audio output device. The server always plays to the default system device. This limits deployment options (containerized, headless, CI, WSL) and prevents users from targeting a specific audio output.

## Goal

Provide a pluggable audio playback backend system for the ziomek server, configurable via config file, CLI flags, and environment variables. Allow users to select among known backends and target a specific playback device.

## Non-Goal

Client audio (gamepad/webview). The server abstraction must be extensible enough that client implementation can reuse the same protocol later, but this spec does not implement client-side playback.

## Requirements

### Config File Support

- Server reads `ziomek_server_config.yaml` from the current working directory first.
- Falls back to `~/.ziomek/ziomek_server_config.yaml` if the current directory file does not exist.
- The client config (scaffolded separately) will be `ziomek_client_config.yaml`, but that is a future task.

### Configuration Precedence

Highest priority wins:

1. CLI flags (`--audio-backend`, `--audio-device`)
2. Environment variables (`ZIOMEK_AUDIO_BACKEND`, `ZIOMEK_AUDIO_DEVICE`)
3. Config file (`ziomek_server_config.yaml`)
4. Hardcoded defaults

### Configurable Backend

- User selects a backend by name.
- Each backend must implement:
  - `play(data: bytes, sample_rate: int) -> None` — single-shot playback
  - `mix_play(data: bytes, sample_rate: int) -> None` — overlapping, non-blocking playback
  - `list_devices() -> list[dict]` — available audio endpoints
  - `supports_mixing: bool` — class attribute

### Configurable Device

- User specifies a device by:
  - `None` or `"default"` — use system default
  - Integer index — use that device index
  - String name — match against `list_devices()` results; raise a clear error if no match
- Device selection is backend-specific; backends that cannot enumerate devices report `[]`.

### Non-Mixing Fallback

- If a backend does not support mixing (`supports_mixing = False`), `mix_play()` falls back to calling `play()` sequentially.
- The caller (TTS engine) is encouraged to check `supports_mixing` before calling `mix_play()`, but the fallback prevents crashes.

### Backend List

- **sounddevice** — current behavior, full mixing, device selection. Default.
- **pygame.mixer** — mixing via channels, limited concurrent voices, device selection via index.
- **pyaudio** — streaming playback, device selection via info dict.
- **playsound** — single-shot only, no device selection (always default).
- **python-rtmixer** — low-latency mixing, Linux-focused; may require fallback on other platforms.
- **noop** — test/dry-run mode, consumes data without playing.

### Client Compatibility

- The `IBackend` protocol must be reusable by the client side. No client implementation here.
- The `AudioPlayer` wrapper that existed in `playback.py` delegates to the selected backend. This pattern is what the client will later replicate.

## Architecture

```
┌──────────────────────────────────────┐
│  Settings (pydantic model)           │
│  - audio_backend: str = "sounddevice"│
│  - audio_device: str | int | None    │
└──────────────┬───────────────────────┘
               │ compose()
               ▼
┌──────────────────────────────────────┐
│  AudioPlayer (thin wrapper)          │
│  def __init__(self, settings: ...)   │
│  def play(...) -> None               │
│  def mix_play(...) -> None           │
└──────────────┬───────────────────────┘
               │ get()
               ▼
┌──────────────────────────────────────┐
│  BackendRegistry (singleton)         │
│  registry.get(name) -> IBackend      │
│  Lazy imports — only load selected   │
│  backend's dependencies              │
└──────────────┬───────────────────────┘
               │
    ┌──────────┼───────────┬──────────┐
    ▼          ▼           ▼          ▼
  sounddevice  pygame     pyaudio  playsound
  rtmixer      noop
```

### File Structure

- `src/ziomek/config.py` — add audio fields, config loading, `Settings.compose()`
- `src/ziomek/tts/backends/base.py` — new, `IBackend` ABC/protocol
- `src/ziomek/tts/backends/__init__.py` — new, `BackendRegistry` singleton
- `src/ziomek/tts/backends/sounddevice.py` — new, wraps current `playback.py` logic
- `src/ziomek/tts/backends/noop.py` — new, test mode
- `src/ziomek/tts/backends/pygame_mixer.py` — new
- `src/ziomek/tts/backends/pyaudio.py` — new
- `src/ziomek/tts/backends/playsound.py` — new
- `src/ziomek/tts/backends/rtmixer.py` — new, Linux-focused, graceful fallback
- `src/ziomek/tts/playback.py` — modified, thin `AudioPlayer` delegating to registry
- `src/ziomek/server.py` — modified, pass `settings` to `AudioPlayer()`
- `src/ziomek/cli.py` — modified, add `--audio-backend`, `--audio-device` flags
- `tests/tts/test_backends.py` — new, backend registry, device selection
- `tests/tts/test_playback.py` — modified, adapt existing tests for wrapper pattern
- `tests/test_config.py` — new, config loading, override precedence

### Error Handling

- **Unknown backend** — `ValueError("Unknown audio backend: X")`
- **Device not found** — `ValueError(f"Device not found: X (available: {devices})")`
- **Backend not available** — missing optional dependency (e.g., `pyaudio` not installed) → `ImportError` caught by registry, backend auto-deregisters with a warning log.
- **rtmixer on non-Linux** — backend self-reports as unavailable; registry excludes it from `list_backends()` with a warning log.
- **Playback errors** — each backend catches exceptions in its playback thread and does not propagate (current behavior preserved).

### Testing

- Backend registry: register, get by name, list backends, unknown backend raises
- Device selection: by index, by name (match and no-match), default, `None`
- Non-mixing fallback: `mix_play()` on a non-mixing backend calls `play()` sequentially
- Config file: load defaults, fallback to home, file < env < CLI precedence
- AudioPlayer: delegates to correct backend, passes args through
- Each backend: unit tests with mocks; sounddevice and noop may run integration tests

### Scaffold Command

- `ziomek scaffold-config` — generates `ziomek_server_config.yaml` in the current directory with all defaults and comments explaining each option.

## Decisions

1. **Non-mixing fallback uses A** — `mix_play()` on non-mixing backends falls back to sequential `play()` calls, not `NotImplementedError`.
2. **Device selection uses C** — accept `None`, integer index, or string name; fall back to default if `None`.
3. **Config precedence** — CLI > env > file > defaults.
4. **Scope is server-only** — client follows as a separate task but the `IBackend` protocol is designed for reuse.
5. **Backend isolation** — each backend is a standalone file; registry imports lazily so optional dependencies only load when selected.
