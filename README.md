# Ziomek — Humanize AI

Humanize AI interaction by making it more natural. Work in progress.

**Two processes:**
- **ziomek server** — TTS synthesis, sprite data, voice caching (port 5003)
- **ziomek client** — gamepad polling, avatar state machine, HTML display (port 5004)

**One extension:**
- **Ziomek — Humanize AI** — thin canvas renderer + Copilot Chat integration

## Quick Start

### Start the TTS server

```bash
uv run python -m ziomek.cli serve --port 5003
```

`uv` auto-creates a `.venv`, downloads dependencies, and installs `ziomek` in development mode from the local package.

`uv` auto-creates a `.venv`, downloads dependencies, and installs `ziomek` in development mode from the local package.

### Start the client (gamepad + avatar display)

```bash
cd python
uv run python -m ziomek.cli client --port 5004 --server-url http://localhost:5003
```bash

This opens a browser window with the avatar display and relays gamepad state to the VS Code extension.

**Alternative launch scripts:**

| Command | What runs |
|---------|-----------|
| `run-ziomek.sh 5003` | TTS server (Linux/macOS) |
| `run-ziomek.bat 5003` | TTS server (Windows) |

### Install and launch the VS Code extension

```bash
cd vscode_extension
npm install
npm run compile
```

Press **F5** in VS Code to launch the extension host. The extension automatically connects to the ziomek client.

Press **F5** in VS Code to launch the extension host. The extension automatically connects to the ziomek client.

## Architecture

```text
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
```text

## Launch Commands

### ziomek server (TTS backend)

```bash
uv run python -m ziomek.cli serve --port 5003 --voice cosette --cache-dir ./voices
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 5003 | HTTP port |
| `--voice` | default | Voice name (cosette) |
| `--cache-dir` | ~ | Voice cache directory |

### ziomek client (gamepad + avatar display)

```bash
cd python
uv run python -m ziomek.cli client --port 5004 --server-url http://localhost:5003
```bash

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 5004 | Client HTTP/WebSocket port |
| `--no-vscode` | false | Disable VS Code WebSocket relay |
| `--no-browser` | false | Disable local browser view |
| `--server-url` | localhost:5003 | TTS server URL |

**Usage modes:**

| Command | What runs |
|---------|-----------|
| `uv run python -m ziomek.cli client` | Browser view + VS Code relay (default) |
| `uv run python -m ziomek.cli client --no-vscode` | Browser view only (no extension needed) |
| `uv run python -m ziomek.cli client --no-browser` | VS Code relay only (headless) |
| `uv run python -m ziomek.cli client --no-browser --no-vscode` | Standalone display only |

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

### Python (ziomek)

```bash
uv sync                           # install dependencies and .venv
uv run python -m ziomek.cli serve # run the TTS server
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
```bash

## File Structure

```text
.
├── src/ziomek/                  # ziomek package (src layout)
│   ├── cli.py                   # Server & client CLI
│   ├── server.py                # TTS server (port 5003)
│   ├── config.py                # Settings
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
│       └── gamepad.py           # Pygame gamepad polling
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
