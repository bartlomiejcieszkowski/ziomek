# ZIOMEK — Plan

## Overview

**ziomek** is a standalone Python package that exposes all Humanize AI backend capabilities (TTS synthesis + avatar rendering) through a local HTTP server. The **VS Code extension** (renamed to **"Ziomek — Humanize AI"**) becomes a thin client — just a UI layer that talks to ziomek via HTTP.

---

## Target Architecture

```
┌─────────────────────────────────────────────┐
│              VS Code Extension               │
│                                              │
│  ┌────────────┐  ┌──────────────────────┐   │
│  │  Avatar     │  │   TTS Controls       │   │
│  │  Panel      │◄─│  (speak, voices,     │   │
│  │  (HTML/JS)  │  │   status)            │   │
│  └────────────┘  └──────────────────────┘   │
│       ▲                    ▲                 │
│       │                    │                 │
│       │  HTTP (JSON)       │  HTTP (JSON)    │
└───────┼────────────────────┼─────────────────┘
        │                    │
        │          ┌─────────▼──────────┐
        │          │   ziomek server    │
        │          │   localhost:5003    │
        │          └─────────┬──────────┘
        │                    │
┌───────┼────────────────────┼──────────────────────────────┐
│       │                    │                              │
│  ┌────▼────┐        ┌──────▼──────┐                       │
│  │ avatar  │        │     tts     │                       │
│  │ module  │        │  module     │                       │
│  │         │        │             │                       │
│  │ State   │        │ PocketTTS   │                       │
│  │ Machine │        │ Integration │                       │
│  │         │        │             │                       │
│  │ Skin    │        │ Audio       │                       │
│  │ Renderer│        │ Playback    │                       │
│  └─────────┘        └─────────────┘                       │
│                                                            │
│  Dependencies: pocket-tts, numpy, torch, sounddevice       │
└────────────────────────────────────────────────────────────┘
```

---

## ziomek Package Structure

```
ziomek/                              # Root package directory (at project level)
│
├── pyproject.toml                   # Package metadata, dependencies, CLI entry point
├── README.md                        # Installation + usage docs
├── LICENSE
│
└── ziomek/                          # Python package
    ├── __init__.py                  # Package entry, version
    │
    ├── server.py                    # HTTP server (FastAPI/Starlette)
    │   └── exposes all API endpoints
    │
    ├── cli.py                       # CLI interface
    │   └── `ziomek serve --port 5003`
    │
    ├── config.py                    # Settings (ports, model paths, cache dirs)
    │
    ├── api/                         # Public API contracts
    │   ├── tts.py                   # TTS endpoint handlers
    │   ├── avatar.py                # Avatar endpoint handlers
    │   └── health.py                # /status, /
    │
    ├── tts/                         # TTS backend module
    │   ├── engine.py                # Pocket TTS model loading & inference
    │   ├── voice.py                 # Voice state management, caching
    │   ├── generate.py              # Text → WAV conversion (base64 response)
    │   └── playback.py              # Audio playback (sounddevice mixing)
    │
    ├── avatar/                      # Avatar backend module
    │   ├── state_machine.py         # State machine logic (ported from TS)
    │   ├── skins.py                 # Skin registry + rendering
    │   ├── sprites.py               # Sprite sheet parsing (PNG → frame grid)
    │   └── display.py               # Display output (canvas-ready image data)
    │
    └── models/                      # Shared types (dataclasses for API payloads)
        ├── audio.py                 # AudioResponse, GenerateRequest, SpeakRequest
        └── avatar.py                # ExpressionState, SpriteData, UpdateRequest
```

---

## API Endpoints

### TTS

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| GET | `/api/tts/voices` | — | `{voices: [...], default: string}` | List available voices |
| GET | `/api/tts/status` | — | `{ready: bool, model_loaded: bool}` | Server/TTS health |
| POST | `/api/tts/generate` | `{text, voice}` | `{audio_b64, duration, sample_rate}` | Generate WAV (no playback) |
| POST | `/api/tts/speak` | `{text, voice}` | `{status: "playing", duration}` | Generate + play audio |

### Avatar

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| GET | `/api/avatar/state` | — | `{expression, cycle_index, message}` | Get current expression |
| POST | `/api/avatar/speak` | `{text, voice, expression?}` | `{status: "playing", duration}` | Generate speech + set expression |
| POST | `/api/avatar/expression` | `{expression, duration_ms?, message?}` | `{ok: bool}` | Force-set expression (for TTS sync) |
| GET | `/api/avatar/sprite` | — | `{sprite_b64, width, height, frame_w, frame_h}` | Get sprite sheet for client rendering |
| POST | `/api/avatar/input` | `{buttons, axes, connected, streaming, error_state}` | `{expression, cycle_index}` | Feed gamepad/VSCode state, get back new expression |

### Health

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| GET | `/status` | — | `{ready, model_loaded, endpoints}` | Server status |
| GET | `/` | — | `{name, version, endpoints}` | Server info |

---

## Porting Strategy: TypeScript → Python

### 1. State Machine (`state-machine.ts` → `avatar/state_machine.py`)

**Direct port** — same logic, different language:
- Expression definitions → Python dataclasses / TypedDict
- Trigger types → Python enums (`TriggerType.BUTTON`, `TriggerType.AXIS`, `TriggerType.VSCODE`, `TriggerType.IDLE`)
- Intensity-based preemption → same algorithm
- `update(input)` → same button/axis level-triggering
- `tick(dtMs)` → cycle advancement, expression transitions
- `setExpression()`, `setMessage()` → direct manipulation

**Key differences:**
- Python doesn't have `setTimeout` → use a callback registry or pass a `now()` function for time-based expiry
- Message expiry: store `expiry_timestamp: float` and check against `now()` (caller provides clock)

### 2. Skin Registry (`skin-registry.ts` → `avatar/skins.py`)

- Skin class → Python `@dataclass` with methods
- `getFrameRow()`, `getFrameCount()`, `getExpressionNames()` → same interface
- `getSpriteBuffer()` → returns PNG bytes from file or base64 string

### 3. Sprite Parsing (`avatar-panel.ts` `_loadSprite()` → `avatar/sprites.py`)

- Parse PNG header: extract width/height from bytes 16-23
- Auto-detect frame rows from `sprite_height / sprite_width` ratio
- Export: `SpriteMetadata` (dimensions, frame count, frame size) + sprite bytes

---

## VS Code Extension: "Ziomek — Humanize AI"

### Before (current)
```
Extension (humanize-ai)
  ├── pocket-tts-service  → spawns python3 process, manages lifecycle
  ├── AvatarStateMachine  → runs in extension host
  ├── Sprite rendering    → reads PNG from disk, computes rows in JS
  └── avatar-panel.ts     → HTML webview, canvas rendering
```

### After (renamed to "Ziomek — Humanize AI")
```
Extension ("Ziomek — Humanize AI") — thin client
  ├── TTSClient           → fetch() to ziomek /api/tts/*
  ├── AvatarClient        → fetch() to ziomek /api/avatar/*
  └── avatar-panel.ts     → HTML webview, canvas rendering (unchanged UI)

ziomek (Python) — full backend
  ├── TTS engine (pocket-tts)
  ├── Avatar state machine
  ├── Sprite parsing
  └── HTTP server on localhost:5003
```

### Extension changes
- `package.json` → rename from `humanize-ai` to `ziomek-humanize` (or similar)
- `package.json` → update `displayName` to `"Ziomek — Humanize AI"`
- Remove `_startServer()`, `_stopServer()`, `_child` process management from `pocket-tts-service.ts`
- Remove `AvatarStateMachine` class → moves to ziomek
- Remove sprite dimension parsing → moves to ziomek
- Replace all internal TTS/avatar logic with HTTP client calls to ziomek

### Extension code to keep
- `avatar-panel.html` — the webview UI (canvas rendering)
- `avatar-panel.ts` — VS Code webview bridge (sends/ receives messages)
- Extension activation, configuration, command definitions
- Gamepad input detection → forwards button/axis data to ziomek via `/api/avatar/input`

---

## Implementation Steps

### Phase 1: Package scaffold
1. Create `ziomek/pyproject.toml` with dependencies (`pocket-tts`, `numpy`, `torch`, `sounddevice`, `scipy`, `fastapi`, `uvicorn`)
2. Create `ziomek/ziomek/__init__.py` — version, package entry
3. Create `ziomek/ziomek/cli.py` — `ziomek serve` CLI using `argparse` / `click`
4. Copy `pocket-tts-server.py` into `ziomek/ziomek/server.py` (restructure)
5. Verify `pip install -e ziomek/` works, `ziomek serve` starts

### Phase 2: TTS module extraction
1. Split `pocket-tts-server.py` into:
   - `ziomek/tts/engine.py` — model loading, `TTSModel` wrapper
   - `ziomek/tts/voice.py` — voice state caching, loading from HF/local paths
   - `ziomek/tts/generate.py` — text → WAV → base64 conversion
   - `ziomek/tts/playback.py` — sounddevice playback with mixing
2. Define dataclasses in `ziomek/models/audio.py`
3. Rewrite `ziomek/api/tts.py` using FastAPI (or keep HTTPServer, but structured)
4. Add `/api/tts/voices`, `/api/tts/status` endpoints
5. Verify all existing endpoints work: `/generate`, `/api/tts/speak`, `/status`

### Phase 3: Avatar module porting
1. Port `AvatarStateMachine` from TS to Python (`ziomek/avatar/state_machine.py`)
   - Expression definitions as dataclasses
   - Trigger types as Enums
   - Intensity preemption algorithm
   - `update()`, `tick()`, `setExpression()`, `setMessage()`
2. Port `SkinRegistry` (`ziomek/avatar/skins.py`)
3. Sprite sheet parser (`ziomek/avatar/sprites.py`) — PNG header parsing
4. Define dataclasses in `ziomek/models/avatar.py`
5. Expose avatar endpoints: `/api/avatar/state`, `/api/avatar/speak`, `/api/avatar/expression`, `/api/avatar/sprite`, `/api/avatar/input`
6. Test state machine independently with unit tests

### Phase 4: Server integration
1. Unify endpoints under single FastAPI app in `ziomek/server.py`
2. Shared startup: load TTS model + avatar assets once at server init
3. Add health/status endpoint showing both TTS and avatar readiness
4. Add graceful shutdown handling
5. Add CORS headers for VS Code webview origin

### Phase 5: Extension client rewrite
1. Rewrite `PocketTTSService` → `ZiomekTTSClient`
   - No process spawning — just HTTP calls
   - Configurable host/port (default `localhost:5003`)
   - `speak()`, `stop()`, `isAvailable()` (check `/api/tts/status`)
2. Rewrite avatar panel to use ziomek endpoints:
   - Fetch sprite sheet from `/api/avatar/sprite` instead of reading PNG from disk
   - Send gamepad/VSCode state to `/api/avatar/input`
   - Get expression state from `/api/avatar/state`
   - TTS+avatar sync via `/api/avatar/speak`
3. Remove `state-machine.ts` and `skin-registry.ts`
4. Update `extension.ts` — new client initialization
5. Test full flow: speak → TTS + avatar expression syncs

### Phase 6: Distribution
1. Create `run-ziomek.sh` / `run-ziomek.bat` launcher scripts
2. Add ziomek to PyPI (or local install via `pip install .`)
3. Create `.vsix` build workflow (GitHub Actions)
4. Update README with client/server setup instructions

---

## Dependencies (ziomek)

```toml
[project]
name = "ziomek"
version = "0.1.0"
description = "Humanize AI backend — TTS + avatar display server"
requires-python = ">=3.10"

dependencies = [
    "pocket-tts>=3.0",
    "torch>=2.0",
    "numpy>=1.24",
    "scipy>=1.10",
    "sounddevice>=0.4",
    "soundfile>=0.12",
    "safetensors>=0.4",
    "fastapi>=0.100",
    "uvicorn[standard]>=0.23",
    "pydantic>=2.0",
    "pillow>=10.0",        # for sprite sheet parsing
    "requests>=2.31",       # for HF model downloads
]
```

---

## Notes

- The avatar panel HTML/CSS/JS stays in the VS Code extension — no change needed there
- Gamepad input detection stays in the extension (Node.js gamepad API) — the extension forwards button/axis data to ziomek via `/api/avatar/input`
- The state machine runs on the ziomek server so avatar logic is consistent regardless of client
- TTS+avatar sync: when a user speaks, `/api/avatar/speak` generates audio AND sets a speaking expression automatically (can be toggled in config)
- Voice caching: `voices/` directory with `.safetensors` files — ziomek manages this directory
