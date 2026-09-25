# Ziomek — Humanize AI

Control VS Code and Copilot Chat with a gamepad. Modular architecture with a standalone Python backend.

**Two processes:**
- **ziomek server** — TTS synthesis, sprite data, voice caching (port 5003)
- **ziomek client** — gamepad polling, avatar state machine, HTML display (port 5004)

**One extension:**
- **Ziomek — Humanize AI** — thin canvas renderer + Copilot Chat integration

## Quick Start

### Install Python packages (uv)

```bash
cd C:/gh/gamify_ai
uv run ziomek serve --port 5003   # first run installs deps, creates .venv
```

`uv` auto-creates a `.venv` from `pyproject.toml`, downloads dependencies, and installs `ziomek` in development mode. You only need to do this once.

### Start the TTS server

```bash
uv run ziomek serve --port 5003
```

### Start the client (gamepad + avatar display)

```bash
uv run ziomek client --port 5004 --server-url http://localhost:5003
```

This opens a browser window with the avatar display and relays gamepad state to the VS Code extension.

**Launch options:**

| Command | What runs |
|---------|----------|
| `ziomek` | Ziomek client (default) |
| `ziomek serve` | TTS server only |
| `ziomek client` | Client only (gamepad + display) |
| `ziomek client --no-vscode` | Client only, no VS Code relay |
| `ziomek client --no-browser` | Client only, no local browser |

### Install and launch the VS Code extension

```bash
cd C:/gh/gamify_ai
npm install
npm run compile
```

Press **F5** in VS Code to launch the extension host. The extension automatically connects to the ziomek client.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ziomek client (port 5004)                            │
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐          │
│  │ pygame       │───→│ State Machine│───→│ HTML/JS Renderer │          │
│  │ gamepad poll │    │ (Python)     │    │ (shared)           │          │
│  └──────────────┘    └──────────────┘    │  Browser/Canvas  │          │
│                                         └──────────────────┘          │
│  ┌────────────────────┐     ┌──────────────────┐                      │
│  │ FastAPI Web Server │───→ │ Local Browser     │                      │
│  │ :5004              │     │ (auto-opened)     │                      │
│  │                    │     └──────────────────┘                      │
│  │ /avatar-view       │                                                │
│  │ /avatar            │   ┌──────────────────┐                         │
│  │ /avatar/sprite     │   │ Extension Canvas  │                         │
│  │ /avatar/state      │   │ (optional relay)  │                         │
│  └────────────────────┘   └──────────────────┘                         │
└──────────────────────────────────────────────────────────────────────────┘
                                                                        │
                                                                        │ WebSocket relay
                                                                        ▼
┌─────────────────────────────┐     └──────────────────────────────────┐
│  VS Code Extension          │     │  ziomek server (port 5003)       │
│  • Canvas rendering         │     │  • TTS synthesis                 │
│  • Copilot Chat integration │     │  • Sprite data                   │
│  • Fetches HTML from client │     │  • Audio playback                │
└─────────────────────────────┘     └──────────────────────────────────┘
````

## Launch Commands

### ziomek server (TTS backend)

```bash
ziomek serve --port 5003 --voice cosette --cache-dir ./voices
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 5003 | HTTP port |
| `--voice` | default | Voice name (cosette) |
| `--cache-dir` | ~ | Voice cache directory |

### ziomek client (gamepad + avatar display)

```bash
uv run ziomek client --port 5004 --server-url http://localhost:5003
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 5004 | Client HTTP/WebSocket port |
| `--no-vscode` | false | Disable VS Code WebSocket relay |
| `--no-browser` | false | Disable local browser view |
| `--server-url` | localhost:5003 | TTS server URL |

**Usage modes:**

| Command | What runs |
|---------|-----------|
| `uv run ziomek client` | Browser view + VS Code relay (default) |
| `uv run ziomek client --no-vscode` | Browser view only (no extension needed) |
| `uv run ziomek client --no-browser` | VS Code relay only (headless) |
| `uv run ziomek client --no-browser --no-vscode` | Standalone display only |

## VS Code Extension Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ziomek.enabled` | true | Enable gamepad input for Ziomek Humanize AI |
| `ziomek.client.url` | http://localhost:5004 | URL of the ziomek client (gamepad relay) |
| `ziomek.tts.url` | http://localhost:5003 | URL of the ziomek TTS server |
| `ziomek.tts.voice` | cosette | Voice identifier for TTS |
| `ziomek.tts.backend` | stub | TTS backend ('stub' or 'ziomek') |
| `ziomek.debounceMs` | 80 | Minimum time between repeated actions (ms) |

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

```bash
# Install dependencies
cd C:/gh/gamify_ai
npm install

# Compile TypeScript
npm run compile

# Run tests
npm test

# Auto-recompile on changes
npm run watch
```

## File Structure

```
.
├── pyproject.toml             # Workspace root (uv workspace config)
├── uv.lock                    # Resolved dependency lockfile
├── ziomek/                    # ziomek Python package
│   ├── pyproject.toml         # Package config
│   ├── run-ziomek.sh          # Launcher script (Linux/macOS)
│   ├── run-ziomek.bat         # Launcher script (Windows)
│   ├── ziomek/
│   │   ├── cli.py             # ziomek server & client CLI
│   │   ├── server.py          # TTS server (port 5003)
│   │   ├── config.py          # Settings
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
│   └── client/                  # ziomek client module
│       ├── cli.py               # ziomek-client CLI
│       ├── server.py            # Client HTTP server (port 5004)
│       ├── gamepad.py           # Pygame gamepad polling
│       └── __init__.py          # Package init
├── client/
│   └── renderer.html            # Shared HTML avatar renderer
├── pyproject.toml               # Package config
├── run-ziomek.sh                # Launcher script (Linux/macOS)
└── run-ziomek.bat               # Launcher script (Windows)

src/                             # VS Code extension
├── extension.ts                 # Main entry point
├── humanize/
│   ├── avatar-panel.ts          # Canvas renderer (reads from client)
│   ├── avatar/
│   │   └── websocket-client.ts  # WebSocket client for state updates
│   └── tts/                     # TTS service abstraction
├── modules/                     # Copilot Chat module system
├── mapping/                     # Input mapping system
└── context.ts                   # Context tracking
```

## Contributing

The module system is extensible. Create a new module by implementing the `GamepadModule` interface in `src/modules/` and registering it in `src/extension.ts`.
