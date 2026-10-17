# Ziomek — Humanize AI

Humanize AI interaction by making it more natural. Work in progress.

**One process:**
- **ziomek** — TTS synthesis, STT, avatar state machine, gamepad polling, WebSocket relay (port 5004)

**One extension:**
- **Ziomek — Humanize AI** — thin canvas renderer + Copilot Chat integration

## Quick Start

### Start the server

```bash
uv run ziomek --port 5004
```

`uv` auto-creates a `.venv`, downloads dependencies, and installs `ziomek` in development mode from the local package.

**Alternative launch scripts:**

| Command | What runs |
|---------|-----------|
| `run-ziomek.sh 5004` | ziomek (Linux/macOS) |
| `run-ziomek.bat 5004` | ziomek (Windows) |

### Install and launch the VS Code extension

```bash
cd vscode_extension
npm install
npm run compile
```

Press **F5** in VS Code to launch the extension host. The extension automatically connects to the ziomek server.

## Architecture

```text
┌───────────────────────────────────────────────────────────────────────┐
│  ziomek (port 5004)                                                   │
│  ┌────────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ TTS Synthesis      │  │ Audio Playback   │  │ Avatar           │   │
│  │ TTSModelWrapper    │  │ BackendRegistry  │  │ State Machine    │   │
│  │ (Coqui TTS)        │  │ pygame / sound-  │  │                  │   │
│  │                    │  │ device / py-     │  │ /                │   │
│  │ /tts/synthesize    │  │ audio / playsound│  │ HTML/JS Renderer │   │
│  │ /tts/cancel        │  │ / noop           │  │ (served by       │   │
│  └────────────────────┘  └──────────────────┘  │ FastAPI)         │   │
│  ┌──────────────────┐  ┌──────────────────┐  └──────────────────┘   │
│  │ pygame           │→ │ Avatar           │  ┌──────────────────┐   │
│  │ gamepad poll     │  │ State Machine    │  │ WebSocket Relay  │   │
│  └──────────────────┘  └──────────────────┘  │ ← Extension      │   │
│  ┌──────────────────┐       ┌──────────────────┐  │ → gamepad state│   │
│  │ STT (Speech-to-  │       │ /docs, /redoc    │  └──────────────────┘   │
│  │ Text)            │       └──────────────────┘                      │
│  │ faster_whisper   │                                              │
│  └──────────────────┘                                              │
└──────────┬──────────────────────────────────────────────────────────┘
           │ WebSocket
           ▼
┌─────────────────────────────┐
│  VS Code Extension          │
│  • Canvas rendering         │
│  • Copilot Chat integration │
│  • Fetches avatar state     │
│    & gamepad relay          │
└─────────────────────────────┘
```

## Launch Commands

### ziomek (unified)

```bash
uv run ziomek --host 0.0.0.0 --port 5004 --log-level INFO --voice cosette --cache-dir ./voices
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | localhost | Host to bind (0.0.0.0 for remote/Docker) |
| `--port` | 5004 | HTTP port |
| `--voice` | default | Voice name (cosette) |
| `--cache-dir` | ~ | Voice cache directory |
| `--log-level` | INFO | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `--no-vscode` | false | Disable VS Code WebSocket relay and gamepad polling |
| `--no-browser` | false | Disable local browser view |
| `--stt-engine` | faster_whisper | STT engine (faster_whisper) |
| `--stt-model` | tiny | STT model (tiny, base, small, medium) |
| `--dev` | false | Enable debug endpoints and debug page |
| `-v, --verbose` | false | Enable DEBUG logging |

**Usage modes:**

| Command | What runs |
|---------|-----------|
| `uv run ziomek` | Full server (browser + VS Code relay + gamepad + STT) |
| `uv run ziomek --no-vscode` | Browser view only (no extension needed) |
| `uv run ziomek --no-browser` | VS Code relay only (headless) |
| `uv run ziomek --no-browser --no-vscode` | Standalone API only |
| `uv run ziomek --dev` | Full server with debug page at `/debug` |
| `uv run ziomek -v` | Full server with verbose DEBUG logging |

### STT (Speech-to-Text)

**HTTP endpoints:**

```bash
# Check STT status
curl http://localhost:5004/api/stt/status

# Start recording
curl -X POST http://localhost:5004/api/stt/start

# Stop recording
curl -X POST http://localhost:5004/api/stt/stop

# One-shot transcription (base64 WAV audio)
curl -X POST http://localhost:5004/api/stt/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_b64": "<base64>", "sample_rate": 16000}'

# Reconfigure engine/model
curl -X POST http://localhost:5004/api/stt/reconfigure \
  -H "Content-Type: application/json" \
  -d '{"engine": "faster_whisper", "model": "base.en"}'

# List available models
curl http://localhost:5004/api/stt/models
```

**WebSocket streaming:**

```bash
# Live transcription via WebSocket
wscat -c ws://localhost:5004/api/stt/stream

# Send commands:
# { "action": "start" }   # Start recording
# { "action": "stop" }    # Stop recording
# { "action": "status" }  # Get status
# { "action": "reconfigure", "engine": "faster_whisper", "model": "base.en" }
```

**Debug page:**

```bash
# Start with debug mode
uv run ziomek --dev

# Open debug page in browser
open http://localhost:5004/debug
```

The debug page provides interactive controls for:
- TTS: voice selection, text input, speak/cancel buttons
- Avatar: expression selection, state display
- STT: engine/model switching, VAD toggle, live transcription, stats
- Gamepad: connection status, button/axis state
- Server: uptime, log level toggle, recent log entries
- Cache: directory, size, file list

## VS Code Extension Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ziomek.enabled` | true | Enable gamepad input for Ziomek Humanize AI |
| `ziomek.client.url` | http://localhost:5004 | URL of the ziomek server |
| `ziomek.tts.url` | http://localhost:5004 | URL of the ziomek TTS server |
| `ziomek.tts.voice` | cosette | Voice identifier for TTS |
| `ziomek.tts.backend` | stub | TTS backend ('stub' or 'ziomek') |
| `ziomek.debounceMs` | 80 | Minimum time between repeated actions (ms) |

## API Endpoints

### TTS (Text-to-Speech)

```bash
# Synthesize speech (returns WAV file)
curl -X POST http://localhost:5004/api/tts/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test"}' \
  -o speech.wav

# List available voices
curl http://localhost:5004/api/tts/voices
```

### STT (Speech-to-Text)

```bash
# Check STT status
curl http://localhost:5004/api/stt/status

# Start/stop recording
curl -X POST http://localhost:5004/api/stt/start
curl -X POST http://localhost:5004/api/stt/stop

# One-shot transcription
curl -X POST http://localhost:5004/api/stt/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_b64": "<base64>", "sample_rate": 16000}'

# Reconfigure engine/model
curl -X POST http://localhost:5004/api/stt/reconfigure \
  -H "Content-Type: application/json" \
  -d '{"engine": "faster_whisper", "model": "base.en"}'

# List available models
curl http://localhost:5004/api/stt/models
```

**WebSocket streaming:**

```bash
wscat -c ws://localhost:5004/api/stt/stream
```

### Avatar

```bash
# Get current state
curl http://localhost:5004/api/avatar/state

# Set expression
curl -X POST http://localhost:5004/api/avatar/expression \
  -H "Content-Type: application/json" \
  -d '{"expression": "happy"}'

# List available expressions
curl http://localhost:5004/api/avatar/expressions
```

### Health

```bash
# Server status (uptime, audio backend, STT info)
curl http://localhost:5004/status
```

## Default Gamepad Mapping

| Input | Action |
|-------|--------|
| A (South) | Send message |
| B (East) | Cancel / Stop streaming |
| X (West) | New chat |
| Y (North) | Open slash menu |
| D-Pad Up | Focus up |
| D-Pad Down | Focus down |
| D-Pad Left | Focus left |
| D-Pad Right | Focus right |
| L1 | Scroll up |
| R1 | Scroll down |
| L2 | Step forward (next code block) |
| R2 | Step backward (previous code block) |
| Start | Toggle Copilot Chat panel |
| Select | Open command palette |
| Left Stick | Scroll chat content |

## Prerequisites

- **uv** (recommended — installs deps and manages venv in one step)
  - Install: <https://docs.astral.sh/uv/getting-started/installation/>
- **Python 3.10+** (auto-managed by uv, or use your system Python)
- **VS Code 1.95+**
- **Gamepad** (Xbox, PlayStation, or any compatible gamepad)
- **pygame-ce** (installed automatically by uv)

## Development

### Python (ziomek)

```bash
uv sync                           # install dependencies and .venv
uv run ziomek                     # run the unified server
uv run pytest tests/              # run tests
uv run ruff check .               # linting
```

### VS Code Extension

```bash
cd vscode_extension
npm install                       # install node modules
npm run compile                   # compile TypeScript to out/
npm test                          # run Jest tests
npm run watch                     # auto-recompile on changes
```


```text
.
├── src/ziomek/                  # ziomek package (src layout)
│   ├── cli.py                   # Unified CLI
│   ├── server.py                # Unified server (TTS + avatar + STT)
│   ├── config.py                # Settings
│   ├── stt.py                   # STT engine (faster_whisper)
│   ├── gamepad.py               # Pygame gamepad polling
│   ├── tts/                     # TTS module
│   │   ├── engine.py            # Pocket TTS model wrapper
│   │   ├── voice.py             # Voice state cache
│   │   ├── generate.py          # WAV generation
│   │   └── playback.py          # Audio player
│   ├── avatar/                  # Avatar module
│   │   ├── state_machine.py     # Expression state machine
│   │   ├── skins.py             # Skin registry
│   │   └── sprites.py           # Sprite sheet parser
│   ├── api/                     # FastAPI endpoints
│   │   ├── tts.py               # /api/tts/*
│   │   ├── avatar.py            # /api/avatar/* + /avatar (WS)
│   │   └── health.py            # /status, /
│   └── client/                  # Client resources (HTML renderer)
│       └── resources/
│           └── renderer.html    # Avatar HTML/JS renderer
├── tests/                       # Python tests
├── pyproject.toml               # Package config (hatchling)
├── uv.lock                      # Dependency lockfile
├── .venv/                       # Virtual env (gitignored)
├── run-ziomek.sh                # Launcher script (Linux/macOS)
├── run-ziomek.bat               # Launcher script (Windows)
├── vscode_extension/            # VS Code extension
│   ├── src/                     # Extension source
│   │   ├── extension.ts         # Main entry point
│   │   ├── humanize/            # Avatar & TTS rendering
│   │   ├── modules/             # Copilot Chat module system
│   │   ├── mapping/             # Input mapping system
│   │   └── context.ts           # Context tracking
│   ├── out/                     # Compiled JS (gitignored)
│   ├── tests/                   # Jest tests
│   ├── package.json             # Extension manifest
│   ├── tsconfig.json            # TypeScript config
│   └── jest.config.js           # Test config
│
├── .github/workflows/           # CI build workflow
├── .vscode/                     # VS Code launch/tasks config
├── debug_tools/                 # JS debug utilities (gamepad, TTS)
├── docs/                        # Documentation
└── voices/                      # Voice safetensors (gitignored)
```

## Contributing

The module system is extensible. Create a new module by implementing the `GamepadModule` interface in `vscode_extension/src/modules/` and registering it in `vscode_extension/src/extension.ts`.
