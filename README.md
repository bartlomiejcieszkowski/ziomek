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
│  │ (Pocket TTS)       │  │ pygame / sound-  │  │                  │   │
│  │                    │  │ device / py-     │  │ /                │   │
│  │ /tts/generate      │  │ audio / playsound│  │ HTML/JS Renderer │   │
│  │ /tts/cancel        │  │ / noop           │  │ (served by       │   │
│  └────────────────────┘  └──────────────────┘  │ FastAPI)         │   │
│  ┌──────────────────┐  ┌──────────────────┐  └──────────────────┘   │
│  │ pygame           │→ │ Avatar           │  ┌──────────────────┐   │
│  │ gamepad poll     │  │ State Machine    │  │ MCP HTTP/stdio   │   │
│  └──────────────────┘  └──────────────────┘  │ (port-based     │   │
│  ┌──────────────────┐       ┌──────────────────┐  │ routing)      │   │
│  │ STT (Speech-to-  │       │ /docs, /redoc    │  └──────────────────┘   │
│  │ Text)            │       └──────────────────┘                      │
│  │ faster_whisper   │                                              │
│  └──────────────────┘                                              │
└──────────┬──────────────────────────────────────────────────────────┘
           │ HTTP / WebSocket / MCP
           ▼
┌─────────────────────────────┐
│  Pi Voice Assistant         │
│  • Keyword-gated STT        │
│  • Gamepad controls         │
│  • TUI dashboard overlay    │
│  • 7 tools (speak, listen,  │
│    status, dashboard, etc.) │
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
| `--no-gamepad` | false | Do not poll gamepad buttons |
| `--no-browser` | false | Do not open the served page in the browser on startup |
| `--stt-engine` | faster_whisper | STT engine (faster_whisper) |
| `--stt-model` | tiny | STT model (tiny, base, small, medium) |
| `--dev` | false | Enable debug endpoints and debug page |
| `-v, --verbose` | false | Enable DEBUG logging |

**Usage modes:**

| Command | What runs |
|---------|-----------|
| `uv run ziomek` | Full server (page in browser + gamepad + STT + MCP) |
| `uv run ziomek --no-browser` | Headless server (page not opened) |
| `uv run ziomek --no-gamepad` | Server without gamepad polling |
| `uv run ziomek --no-browser --no-gamepad` | Standalone API only |
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

## Pi Voice Assistant Extension

Install and configure the Pi extension for hands-free voice interaction with the ziomek server.

### Installation

```bash
cd pi-ziomek
npm install
npm run build
```

Configure Pi to load the extension by adding to your Pi configuration:

```json
{
  "extensions": ["pi-ziomek/dist/index.js"]
}
```

### Configuration

The Pi extension reads its configuration from `~/.pi/agent/extensions/pi-ziomek/config.json`.

| Setting | Default | Description |
|---------|---------|-------------|
| `voice.serverUrl` | http://localhost:5004 | URL of the ziomek server |
| `voice.keyword` | ziomek | Keyword to activate voice commands (case-insensitive prefix match) |
| `voice.keywords` | ["ziomek"] | List of keywords that activate voice mode |
| `voice.maxListenDuration` | 5 | Maximum continuous listening duration (seconds) |
| `gamepad.enabled` | true | Enable gamepad input |
| `gamepad.pollIntervalMs` | 2000 | Gamepad polling interval (ms) |
| `gamepad.debounceMs` | 1000 | Minimum time between repeated button actions (ms) |
| `gamepad.buttonMap` | — | Button index → action mapping (see below) |
| `dashboard.enabled` | true | Enable TUI dashboard overlay |
| `dashboard.autoShow` | true | Show dashboard on extension load |
| `dashboard.refreshIntervalMs` | 2000 | Dashboard refresh interval (ms) |

**Available gamepad buttons:**

| Button | Index | Default Action |
|--------|-------|---------------|
| A | 0 | `listen_short` |
| B | 1 | `cycle_responses` |
| X | 2 | `listen_long` |
| Y | 3 | `tts_speak_last` |
| LB | 4 | `prev_response` |
| RB | 5 | `next_response` |
| D-Pad Up | 12 | `history_up` |
| D-Pad Down | 13 | `history_down` |
| Start | 9 | `toggle_dashboard` |
| Select | 8 | `show_status` |

### Tools

The extension registers the following tools in Pi:

| Tool | Description |
|------|-------------|
| `ziomek_voice_speak` | Send text to TTS for playback |
| `ziomek_voice_listen` | Connect STT, wait for transcription, return "User said: ..." |
| `ziomek_voice_start` | Start continuous listening with keyword gating |
| `ziomek_voice_stop` | Stop continuous listening |
| `ziomek_voice_status` | Return current mode, engine, model info |
| `ziomek_voice_transcribe` | One-shot transcription (placeholder) |
| `ziomek_gamepad_state` | Return gamepad connection status and state |

### Keywords

The extension uses **keyword gating** to activate voice commands. A keyword is a case-insensitive prefix match — the keyword is stripped from the transcription before being sent to the agent.

Example: if the keyword is `ziomek` and the user says:

```
"ziomek, continue"
```

The extension sends only `continue` to the agent.

Keywords are configurable via `voice.keyword` and `voice.keywords` in the config file.

### Dashboard

The TUI dashboard overlay shows:

- **Status indicator**: 🔴 disconnected, 🟡 connecting, 🟢 connected
- **Engine info**: STT engine, model, current state
- **Live transcription**: last 5 transcribed messages
- **Gamepad status**: connection status, current button presses
- **Recent activity**: last 3 actions (tool calls, events)

Toggle the dashboard at any time with the `toggle_dashboard` gamepad action or the `/dashboard` slash command.

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

## Default Gamepad Mapping (Pi Extension)

| Input | Action |
|-------|--------|
| A (South) | Start short voice listening |
| B (East) | Cycle responses |
| X (West) | Start long voice listening |
| Y (North) | Re-speak last TTS output |
| D-Pad Up | Scroll history up |
| D-Pad Down | Scroll history down |
| LB | Previous response |
| RB | Next response |
| Start | Toggle dashboard |
| Select | Show status |

## Prerequisites

- **uv** (recommended — installs deps and manages venv in one step)
  - Install: <https://docs.astral.sh/uv/getting-started/installation/>
- **Python 3.10+** (auto-managed by uv, or use your system Python)
- **Node.js 22+** (for Pi extension development)
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

### Pi Voice Assistant Extension

```bash
cd pi-ziomek
npm install                       # install node modules
npm run build                     # compile TypeScript to dist/
npm test                          # run Vitest tests
npm run dev                       # auto-compile on changes
```

The Pi extension compiles to `pi-ziomek/dist/`. Add the compiled output to your Pi configuration:

```json
{
  "extensions": ["pi-ziomek/dist/index.js"]
}
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
├── pi-ziomek/                   # Pi Voice Assistant extension
│   ├── src/                     # Source TypeScript
│   │   ├── index.ts             # Extension factory
│   │   ├── config.ts            # Config module (load/save/merge)
│   │   ├── tts-client.ts        # TTS API client
│   │   ├── stt-client.ts        # STT API client (WebSocket)
│   │   ├── keyword.ts           # Keyword gating (match/strip)
│   │   ├── gamepad.ts           # Gamepad manager
│   │   ├── dashboard.ts         # TUI dashboard overlay
│   │   ├── tools.ts             # Tool definitions
│   │   └── lifecycle.ts         # Extension lifecycle hooks
│   ├── dist/                    # Compiled output
│   ├── tests/                   # Vitest tests
│   ├── package.json             # Extension manifest
│   └── tsconfig.json            # TypeScript config
│
├── vscode_extension/            # (deprecated — unmaintained) VS Code extension
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

The Pi extension is extensible. Add new features by implementing:

1. New tools in `pi-ziomek/src/tools.ts` (register via `registerTool()`)
2. New gamepad actions in `pi-ziomek/src/gamepad.ts` (extend `buttonMap`)
3. New dashboard widgets in `pi-ziomek/src/dashboard.ts` (extend state update methods)
4. New lifecycle hooks in `pi-ziomek/src/lifecycle.ts` (register via `on()` events)
