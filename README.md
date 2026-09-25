# Ziomek — Humanize AI

Control VS Code and Copilot Chat with a gamepad. Modular architecture for extensible gamepad integration. Connects to a locally running [ziomek](https://github.com/your-org/ziomek) TTS server for voice synthesis and avatar display.

## Features

- **Copilot Chat Control**: Send messages, start new chats, navigate responses
- **VS Code Navigation**: Focus up/down/left/right, scroll through content
- **Context Aware**: Behaves differently based on what you're focused on
- **TTS Integration**: Voice synthesis via ziomek server (localhost:5003)
- **Avatar Display**: Animated avatar synchronized with speech and gamepad input
- **Fully Configurable**: Remap any button, axis, or trigger via VS Code settings

## Prerequisites

### ziomek Server (Python backend)

The extension requires a locally running ziomek server for TTS and avatar rendering:

```bash
# Install ziomek
pip install ziomek  # or clone and run: pip install -e .

# Start the server (default port: 5003)
ziomek serve --port 5003
```

### VS Code Extension

1. Build: `npm run compile`
2. Press F5 in VS Code to launch extension host
3. Connect your gamepad

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

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ziomek.enabled` | `true` | Enable gamepad input for Ziomek Humanize AI |
| `ziomek.tts.url` | `http://localhost:5003` | URL of the ziomek TTS server |
| `ziomek.tts.port` | `5003` | Port for the ziomek TTS server |
| `ziomek.tts.voice` | `cosette` | Voice identifier for TTS |
| `ziomek.pollingIntervalMs` | `16` | Gamepad polling interval (ms) |
| `ziomek.debounceMs` | `80` | Minimum time between repeated actions (ms) |

## Development

```bash
npm install
npm run watch      # Auto-recompile on changes
npm test           # Run tests
```

## Architecture

```
┌─────────────────┐         HTTP          ┌──────────────────┐
│  VS Code Ext    │ ◄──────────────────► │  ziomek Server   │
│  (ziomek.humanize│    localhost:5003    │  (Python/FastAPI) │
│  -ai)           │                        │                  │
│                 │                        │  - TTS Synthesis │
│  - Gamepad API  │                        │  - Avatar State  │
│  - Webviews     │                        │  - Sprite Sheet  │
└─────────────────┘                        └──────────────────┘
```

The extension is a thin HTTP client that manages gamepad input and webview UI, while all TTS and avatar rendering is handled by the ziomek Python server.

## Contributing

The module system is extensible. Create a new module by implementing the `GamepadModule` interface in `src/modules/` and registering it in `src/extension.ts`.
